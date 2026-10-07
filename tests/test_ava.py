from pathlib import Path

from ufmt_agent.ava import extract_deliveries
from ufmt_agent.browser_ava import BrowserAvaClient


def test_extracts_dated_deliveries():
    html = (Path(__file__).parent / "fixtures" / "activities.html").read_text()
    deliveries = {item.source_id: item for item in extract_deliveries(html, "https://ava.ufmt.br/")}
    assert set(deliveries) == {"moodle:42", "moodle:52"}
    assert deliveries["moodle:42"].all_day is False
    assert deliveries["moodle:42"].due_at.hour == 23
    assert deliveries["moodle:52"].all_day is True


def test_extracts_moodle_calendar_due_event_timestamp():
    html = """
    <td data-day-timestamp="1791172800">
      <div data-region="day-content"><ul>
        <li data-region="event-item" data-event-eventtype="due">
          <a href="/mod/assign/view.php?id=99">Relatório final está marcado(a) para esta data</a>
        </li>
      </ul></div>
    </td>
    """
    deliveries = extract_deliveries(html, "https://avagraduacao.ufmt.br/", "America/Cuiaba")
    assert len(deliveries) == 1
    assert deliveries[0].source_id == "moodle:99"
    assert deliveries[0].due_at.date().isoformat() == "2026-10-05"
    assert deliveries[0].all_day is True


def test_extracts_course_from_breadcrumb_not_global_menu():
    html = """
    <nav><a href="/course/view.php?id=1">Manuais do AVA</a></nav>
    <ol class="breadcrumb"><li><a href="/course/view.php?id=8">Criptografia Aplicada</a></li></ol>
    """
    assert BrowserAvaClient._course_name_from_html(html) == "Criptografia Aplicada"


def test_extracts_full_course_name_from_course_page():
    html = '<header id="page-header"><h1>Segurança da Informação</h1></header>'
    assert BrowserAvaClient._course_full_name_from_html(html) == "Segurança da Informação"


def test_prefers_full_course_name_over_short_code():
    assert BrowserAvaClient._name_score("20262 - CC - Projeto de Compiladores") > BrowserAvaClient._name_score("2026231010900156CC")


def test_removes_period_prefix_from_course_card_name():
    assert BrowserAvaClient._display_course_name("20262 - CC - Projeto de Compiladores") == "CC - Projeto de Compiladores"
    assert BrowserAvaClient._display_course_name("20262 - SI - MATEMÁTICA DISCRETA") == "SI - MATEMÁTICA DISCRETA"
    assert BrowserAvaClient._display_course_name("Curso sem período") == "Curso sem período"


def test_normalizes_accessibility_text_and_duplicate_course_name():
    name = "Curso é favorito Nome do curso 20262 - CC - Inovação e Empreendedorismo 20262 - CC - Inovação e Empreendedorismo"
    assert BrowserAvaClient._display_course_name(name) == "CC - Inovação e Empreendedorismo"
