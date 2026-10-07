from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import Delivery

_DUE = re.compile(r"(?:prazo|entrega|vence|due)\s*(?:até|em|:)?\s*(\d{1,2}/\d{1,2}/\d{2,4})(?:\s*(?:às|as)?\s*(\d{1,2}:\d{2}))?", re.I)


class AvaError(RuntimeError):
    pass


class MoodleAvaClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        # O AVA pode recusar clientes HTTP genéricos mesmo quando o formulário
        # é tradicional; usamos cabeçalhos equivalentes aos do Chrome Android.
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self._launch_diagnostic = "nenhum link de lançamento encontrado"

    def login(self) -> None:
        page = self.session.get(self.settings.login_url, timeout=30)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        form = soup.select_one("form")
        if not form:
            raise AvaError("Formulário de login não encontrado")
        inputs = form.select("input[name]")
        payload = {input_.get("name"): input_.get("value", "") for input_ in inputs}
        payload[self.settings.username_field] = self.settings.username
        payload[self.settings.password_field] = self.settings.password
        self._fill_detected_credentials(inputs, payload)
        target = urljoin(self.settings.login_url, form.get("action") or self.settings.login_url)
        origin = urlparse(self.settings.login_url)
        response = self.session.post(
            target,
            data=payload,
            headers={"Referer": self.settings.login_url, "Origin": f"{origin.scheme}://{origin.netloc}"},
            timeout=30,
        )
        response.raise_for_status()
        if response.url.rstrip("/") == self.settings.login_url.rstrip("/") or self._looks_like_login(response.text):
            response_soup = BeautifulSoup(response.text, "html.parser")
            error = response_soup.select_one("#loginerrormessage, .alert-danger, [role='alert']")
            detail = f" Mensagem do AVA: {error.get_text(' ', strip=True)}" if error else ""
            raise AvaError("Login no AVA recusado; confirme URL, RGA, senha e nomes dos campos." + detail)

        # O AVA de graduação atual usa o Portal de Sistemas como provedor de
        # identidade. As navegações intermediárias fazem parte do SSO e
        # estabelecem cookies em sistemas.ufmt.br, academico-siga.ufmt.br e
        # avagraduacao.ufmt.br, respectivamente.
        for label, url in (
            ("lista de sistemas do Portal", self.settings.portal_apps_url),
            ("início do SIGA", self.settings.academic_home_url),
            ("Sala Virtual", self.settings.sso_url),
            ("entrada do AVA", self.settings.ava_entry_url),
        ):
            if not url:
                continue
            sso = self.session.get(url, timeout=30)
            sso.raise_for_status()
            if self._looks_like_login(sso.text):
                raise AvaError(
                    f"A sessão SSO foi recusada em {label}; destino: {sso.url}. "
                    f"Diagnóstico da Sala Virtual: {self._launch_diagnostic}. "
                    "Não foram registrados cookies ou credenciais."
                )
            if label == "Sala Virtual":
                self._open_ava_launch(sso)

    def _open_ava_launch(self, response) -> None:
        """Segue o link de lançamento do AVA exibido pela Sala Virtual.

        O SIGA pode renderizar esse link para uma nova aba, em vez de enviá-lo
        como redirecionamento HTTP. Requests não abre abas, por isso o link
        precisa ser seguido explicitamente na mesma sessão.
        """
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = [
            urljoin(response.url, anchor["href"])
            for anchor in soup.select("a[href]")
            if "avagraduacao.ufmt.br" in anchor["href"]
        ]
        if not candidates:
            # Algumas versões inserem a URL em um handler JavaScript.
            candidates = re.findall(r"https?://avagraduacao\.ufmt\.br[^\"'\s<]+", response.text)
        if not candidates:
            return
        self._launch_diagnostic = "link de lançamento encontrado"
        launch = self.session.get(
            candidates[0],
            headers={"Referer": response.url},
            timeout=30,
        )
        launch.raise_for_status()
        parsed = urlparse(launch.url)
        self._launch_diagnostic = (
            "link de lançamento encontrado; destino sem parâmetros: "
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        )

    def _fill_detected_credentials(self, inputs, payload: dict[str, str]) -> None:
        """Preenche campos comuns de portais institucionais além dos nomes configurados.

        O Portal/AVA pode identificar o usuário pelo RGA. Os nomes dos campos variam entre versões,
        então usamos atributos semânticos do próprio HTML como fallback.
        """
        for input_ in inputs:
            name = input_.get("name")
            if not name:
                continue
            metadata = " ".join(
                str(input_.get(attribute, ""))
                for attribute in ("name", "id", "type", "placeholder", "autocomplete", "aria-label")
            ).casefold()
            if input_.get("type", "").casefold() == "password" or "senha" in metadata or "password" in metadata:
                payload[name] = self.settings.password
            elif any(marker in metadata for marker in ("cpf", "usuário", "usuario", "username", "login", "rga")):
                payload[name] = self.settings.username

    @staticmethod
    def _looks_like_login(html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(soup.select_one('input[type="password"]'))

    def fetch_deliveries(self) -> list[Delivery]:
        response = self.session.get(self.settings.activities_url, timeout=30)
        response.raise_for_status()
        if self._looks_like_login(response.text):
            raise AvaError("Sessão expirada ao consultar atividades")
        return extract_deliveries(response.text, response.url, self.settings.timezone)


def _source_id(url: str, course: str, title: str) -> str:
    activity_id = parse_qs(urlparse(url).query).get("id", [None])[0]
    if activity_id:
        return f"moodle:{activity_id}"
    normalized = f"{course}|{title}".casefold().strip()
    return "text:" + hashlib.sha256(normalized.encode()).hexdigest()[:24]


def _due(text: str, timezone: str) -> tuple[datetime | None, bool]:
    match = _DUE.search(" ".join(text.split()))
    if not match:
        return None, False
    date_text, time_text = match.groups()
    for pattern in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            date = datetime.strptime(date_text, pattern)
            if not time_text:
                return date.replace(tzinfo=ZoneInfo(timezone)), True
            hour, minute = map(int, time_text.split(":"))
            return date.replace(hour=hour, minute=minute, tzinfo=ZoneInfo(timezone)), False
        except ValueError:
            continue
    return None, False


def extract_deliveries(html: str, base_url: str, timezone: str = "America/Cuiaba") -> list[Delivery]:
    """Extrai atividades Moodle usuais; os seletores podem ser ampliados após validação real."""
    soup = BeautifulSoup(html, "html.parser")
    deliveries: dict[str, Delivery] = {}
    for anchor in soup.select('a[href*="mod/assign"], a[href*="mod/quiz"], a[href*="mod/workshop"]'):
        container = anchor.find_parent(["li", "div", "article", "tr"]) or anchor
        raw_text = container.get_text(" ", strip=True)
        due_at, all_day = _due(raw_text, timezone)
        # No calendário mensal do Moodle atual, o texto do evento não traz a
        # data. Ela está no timestamp da célula de dia que contém um evento
        # com tipo "due" (prazo de entrega).
        event = anchor.find_parent("li", attrs={"data-region": "event-item"})
        day = event.find_parent("td", attrs={"data-day-timestamp": True}) if event else None
        if event and event.get("data-event-eventtype") == "due" and day:
            try:
                due_at = datetime.fromtimestamp(int(day["data-day-timestamp"]), tz=ZoneInfo(timezone))
                all_day = True
            except (TypeError, ValueError, OSError):
                pass
        if not due_at:
            continue
        url = urljoin(base_url, anchor["href"])
        title = anchor.get_text(" ", strip=True)
        course_node = container.find_previous(attrs={"data-course-name": True})
        course = course_node.get("data-course-name") if course_node else "AVA UFMT"
        source_id = _source_id(url, course, title)
        deliveries[source_id] = Delivery(source_id, course, title, url, due_at, all_day, raw_text)
    return list(deliveries.values())
