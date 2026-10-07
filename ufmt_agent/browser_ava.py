from __future__ import annotations

import shutil
import re
from dataclasses import replace
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .ava import AvaError, _source_id, extract_deliveries
from .config import Settings
from .models import Delivery


class BrowserAvaClient:
    """Cliente AVA via Chromium real, compatível com o Termux."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._diagnostics: dict[str, object] = {}

    def fetch_deliveries(self) -> list[Delivery]:
        html, url, courses = self._load_page(include_courses=True)
        return [
            replace(delivery, course=courses.get(delivery.source_id, delivery.course))
            for delivery in extract_deliveries(html, url, self.settings.timezone)
        ]

    def inspect(self) -> dict[str, object]:
        html, url, courses = self._load_page(include_courses=True)
        deliveries = extract_deliveries(html, url, self.settings.timezone)
        return {
            "page_url": url.split("?", 1)[0],
            "detected_deliveries": len(deliveries),
            "deliveries": [
                {"course": item.course, "title": item.title, "due_at": item.due_at.isoformat()}
                for item in deliveries
            ],
            "resolved_courses": courses,
            "course_diagnostics": self._diagnostics,
        }

    def _load_page(self, include_courses: bool = False) -> tuple[str, str, dict[str, str]]:
        try:
            from selenium import webdriver
            from selenium.common.exceptions import TimeoutException, WebDriverException
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise AvaError("Selenium não está instalado; execute bin/setup_termux.sh novamente.") from exc

        browser = self.settings.browser_executable or shutil.which("chromium-browser") or shutil.which("chromium")
        driver_path = shutil.which("chromedriver")
        if not browser or not driver_path:
            raise AvaError("Chromium ou ChromeDriver não encontrado no Termux")
        options = Options()
        options.binary_location = browser
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"--user-data-dir={self.settings.browser_profile_path}")
        try:
            driver = webdriver.Chrome(service=Service(driver_path), options=options)
            driver.set_page_load_timeout(45)
            driver.implicitly_wait(12)
            driver.get(self.settings.activities_url)
            if "/login" in driver.current_url.casefold() or driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]'):
                username = driver.find_element(By.CSS_SELECTOR, '#username, input[name="username"], input[name*="rga" i]')
                password = driver.find_element(By.CSS_SELECTOR, '#password, input[type="password"]')
                username.clear()
                username.send_keys(self.settings.username)
                password.send_keys(self.settings.password)
                password.submit()
                WebDriverWait(driver, 30).until(
                    lambda page: "/login" not in page.current_url.casefold()
                    and not page.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
                )
                driver.get(self.settings.activities_url)
            if "/login" in driver.current_url.casefold() or driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]'):
                raise AvaError("O Chromium não conseguiu concluir o login do AVA")
            html, url = driver.page_source, driver.current_url
            courses = self._course_names(driver, html, url) if include_courses else {}
            return html, url, courses
        except TimeoutException as exc:
            raise AvaError("O AVA demorou para responder no Chromium") from exc
        except WebDriverException as exc:
            raise AvaError(f"Falha ao iniciar/controlar o Chromium: {exc.msg}") from exc
        finally:
            try:
                driver.quit()
            except UnboundLocalError:
                pass

    def _course_names(self, driver, dashboard_html: str, dashboard_url: str) -> dict[str, str]:
        """Relaciona cada atividade à disciplina exibida em Meus cursos."""
        dashboard = BeautifulSoup(dashboard_html, "html.parser")
        catalog = self._course_catalog(driver, dashboard_url)
        links = {
            anchor["href"] for anchor in dashboard.select(
                'a[href*="mod/assign"], a[href*="mod/quiz"], a[href*="mod/workshop"]'
            )
        }
        courses: dict[str, str] = {}
        failed_links: list[str] = []
        for href in links:
            try:
                driver.get(urljoin(dashboard_url, href))
                detail = BeautifulSoup(driver.page_source, "html.parser")
                breadcrumb = detail.select_one(".breadcrumb") or detail
                course_link = list(breadcrumb.select('a[href*="course/view.php"]'))
                if not course_link:
                    continue
                course_id = self._course_id(course_link[-1].get("href", ""))
                course = catalog.get(course_id, course_link[-1].get_text(" ", strip=True))
                if course:
                    courses[_source_id(href, course, "")] = course
            except Exception:
                # Uma atividade inacessível conserva o rótulo genérico.
                failed_links.append(href)
                continue
        self._diagnostics = {
            "catalog_courses": catalog,
            "activity_links": len(links),
            "unresolved_activity_links": len(failed_links),
        }
        return courses

    def _course_catalog(self, driver, dashboard_url: str) -> dict[str, str]:
        driver.get(urljoin(dashboard_url, "/my/courses.php"))
        # Os cartões são carregados após o documento principal. A espera
        # implícita acima garante que a consulta só prossiga quando o catálogo
        # dinâmico estiver presente, como já fazíamos no navegador desktop.
        driver.find_elements("css selector", 'div.card a.coursename[href*="course/view.php"]')
        soup = BeautifulSoup(driver.page_source, "html.parser")
        catalog: dict[str, str] = {}
        for anchor in soup.select('div.card a.coursename[href*="course/view.php"]'):
            course_id = self._course_id(anchor.get("href", ""))
            name = self._display_course_name(anchor.get_text(" ", strip=True))
            if course_id and name:
                catalog[course_id] = name
        return catalog

    @staticmethod
    def _course_id(url: str) -> str | None:
        return parse_qs(urlparse(url).query).get("id", [None])[0]

    @staticmethod
    def _display_course_name(name: str) -> str:
        """Remove apenas o período (por exemplo, 20262 -) do cartão."""
        match = re.search(r"\b\d{5}\s*-\s*", name)
        label = name[match.start():] if match else name
        label = re.sub(r"^(.+?)\s+\1$", r"\1", label).strip()
        return re.sub(r"^\d{5}\s*-\s*", "", label).strip()
