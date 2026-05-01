from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
os.chdir(ROOT)
os.environ.setdefault("ATLASTRACE_HOME", str((ROOT / ".atlastrace").resolve()))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atlastrace.cli import main as cli_main  # noqa: E402
from atlastrace.services.cases import create_case, get_case  # noqa: E402
from atlastrace.services.ingest import IDENTITY_TEMPLATES  # noqa: E402
from atlastrace.settings import Settings  # noqa: E402
from atlastrace.storage import Database  # noqa: E402
from atlastrace.ui import clear_screen, print_banner, print_error, print_line, print_section  # noqa: E402
from atlastrace.utils import slugify  # noqa: E402


def pause() -> None:
    try:
        input("\nAppuie sur ENTREE pour revenir au menu...")
    except EOFError:
        pass


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix} : ").strip()
    if value:
        return value
    return default or ""


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "O/n" if default else "o/N"
    value = input(f"{prompt} [{hint}] : ").strip().lower()
    if not value:
        return default
    return value in {"o", "oui", "y", "yes", "1"}


def normalize_case_slug(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if any(token in candidate for token in ("\\", "/", ":")):
        extracted = Path(candidate.rstrip("\\/")).name
        if extracted:
            candidate = extracted
    return slugify(candidate)


def case_exists(case_slug: str) -> bool:
    settings = Settings.from_env()
    settings.ensure_home()
    db = Database(settings.db_path)
    db.ensure_schema()
    try:
        get_case(db, case_slug)
        return True
    except LookupError:
        return False


def maybe_create_case(case_slug: str) -> None:
    if case_exists(case_slug):
        return
    print_error(f"Dossier d'enquete introuvable: {case_slug}")
    if not ask_yes_no("Le creer maintenant ?", True):
        return
    title = ask("Titre du nouveau dossier", case_slug)
    settings = Settings.from_env()
    settings.ensure_home()
    db = Database(settings.db_path)
    db.ensure_schema()
    create_case(db, settings, title=title, slug=case_slug, description="")
    print_line(f"Dossier cree automatiquement -> {case_slug}")


def ask_case_slug(*, must_exist: bool = True) -> str:
    raw = ask("Slug du dossier (pas le chemin Windows)")
    normalized = normalize_case_slug(raw)
    if raw and normalized and raw != normalized:
        print_line(f"Slug normalise automatiquement -> {normalized}")
    if normalized and must_exist:
        maybe_create_case(normalized)
    return normalized


def run_command(argv: list[str]) -> None:
    display_argv = list(argv)
    if display_argv and display_argv[0] == "password-check" and "--password" in display_argv:
        index = display_argv.index("--password")
        if index + 1 < len(display_argv):
            display_argv[index + 1] = "********"
    print_line(f"> atlastrace {' '.join(display_argv)}")
    code = cli_main(argv)
    if code != 0:
        print_error(f"Commande terminee avec le code {code}.")


def program_catalog() -> dict[str, list[tuple[str, str, callable]]]:
    return {
        "Core": [
            ("01", "Initialiser le workspace", action_init),
            ("02", "Creer un dossier d'enquete", action_case_create),
            ("03", "Lister les dossiers d'enquete", action_case_list),
            ("04", "Ajouter une note", action_note_add),
            ("05", "Voir tous les modules", action_modules),
        ],
        "Entities": [
            ("06", "Ajouter une personne", action_add_person),
            ("07", "Ajouter une organisation", action_add_org),
            ("08", "Ajouter un email", action_add_email),
            ("09", "Ajouter un telephone", action_add_phone),
            ("10", "Ajouter un domaine", action_add_domain),
            ("11", "Ajouter une URL", action_add_url),
            ("12", "Ajouter un pseudo / handle", action_add_handle),
        ],
        "Data & Correlation": [
            ("13", "Importer un document", action_doc_import),
            ("14", "Importer un dataset", action_dataset_import),
            ("15", "Correlater les datasets", action_correlate),
            ("16", "Demo de correlation prete a l'emploi", action_demo_overlap),
        ],
        "Recon & Evidence": [
            ("17", "Capturer une page web publique", action_web_capture),
            ("18", "Chercher un pseudo sur beaucoup de sites", action_identity_map),
            ("19", "Afficher les sites de recherche de pseudos", action_show_sites),
            ("20", "Inspecter un media", action_media_inspect),
            ("21", "Preparer un archivage web", action_archive),
        ],
        "Breach & Export": [
            ("22", "Verifier un compte dans les breaches (HIBP)", action_breach_check),
            ("23", "Verifier un mot de passe (HIBP range)", action_password_check),
            ("24", "Exporter le rapport Markdown", action_report_md),
            ("25", "Exporter le graphe Mermaid", action_report_graph),
        ],
    }


def all_actions() -> dict[str, callable]:
    mapping: dict[str, callable] = {}
    for items in program_catalog().values():
        for code, _label, handler in items:
            mapping[code] = handler
    return mapping


def show_menu() -> None:
    clear_screen()
    print_banner()
    print_section(
        "MENU PRINCIPAL",
        [
            "AtlasTrace reprend un style toolbox plus propre, avec categories et selection numerique.",
            "Choisis simplement un numero, puis suis les invites.",
            "00 = quitter",
        ],
    )

    for section_name, items in program_catalog().items():
        lines = [f"[{code}] {label}" for code, label, _handler in items]
        print_section(section_name, lines)


def action_init() -> None:
    run_command(["init"])


def action_case_create() -> None:
    title = ask("Titre du dossier")
    slug = normalize_case_slug(ask("Slug personnalise", ""))
    description = ask("Description", "")
    argv = ["case-create", title]
    if slug:
        argv += ["--slug", slug]
    if description:
        argv += ["--description", description]
    run_command(argv)


def action_case_list() -> None:
    run_command(["case-list"])


def action_note_add() -> None:
    case_slug = ask_case_slug(must_exist=True)
    title = ask("Titre de la note")
    body = ask("Contenu de la note")
    run_command(["note-add", case_slug, title, body])


def entity_helper(kind: str, label: str) -> None:
    case_slug = ask_case_slug(must_exist=True)
    value = ask(label)
    source = ask("Source", "manual")
    confidence = ask("Confiance", "0.7")
    run_command(
        [
            "entity-add",
            case_slug,
            kind,
            value,
            "--source",
            source,
            "--confidence",
            confidence,
        ]
    )


def action_add_person() -> None:
    entity_helper("person", "Nom de la personne")


def action_add_org() -> None:
    entity_helper("organization", "Nom de l'organisation")


def action_add_email() -> None:
    entity_helper("email", "Adresse email")


def action_add_phone() -> None:
    entity_helper("phone", "Numero de telephone")


def action_add_domain() -> None:
    entity_helper("domain", "Nom de domaine")


def action_add_url() -> None:
    entity_helper("url", "URL")


def action_add_handle() -> None:
    entity_helper("handle", "Pseudo / handle")


def action_doc_import() -> None:
    case_slug = ask_case_slug(must_exist=True)
    path = ask("Chemin du document")
    label = ask("Label", "")
    argv = ["doc-import", case_slug, path]
    if label:
        argv += ["--label", label]
    run_command(argv)


def action_dataset_import() -> None:
    case_slug = ask_case_slug(must_exist=True)
    path = ask("Chemin du dataset")
    label = ask("Label du dataset", Path(path).stem if path else "")
    argv = ["dataset-import", case_slug, path]
    if label:
        argv += ["--label", label]
    run_command(argv)


def action_correlate() -> None:
    case_slug = ask_case_slug(must_exist=True)
    min_sources = ask("Nombre minimal de sources", "2")
    output = ask("Chemin de sortie optionnel", "")
    argv = ["correlate", case_slug, "--min-sources", min_sources]
    if output:
        argv += ["--output", output]
    run_command(argv)


def action_demo_overlap() -> None:
    print_line("Creation d'une demo complete avec deux datasets qui se recoupent.")
    run_command(["case-create", "Overlap Demo Auto", "--slug", "overlap-demo-auto"])
    run_command(
        [
            "dataset-import",
            "overlap-demo-auto",
            str(ROOT / "samples" / "overlap_a.txt"),
            "--label",
            "source-a",
        ]
    )
    run_command(
        [
            "dataset-import",
            "overlap-demo-auto",
            str(ROOT / "samples" / "overlap_b.txt"),
            "--label",
            "source-b",
        ]
    )
    run_command(["correlate", "overlap-demo-auto"])


def action_web_capture() -> None:
    case_slug = ask_case_slug(must_exist=True)
    url = ask("URL publique")
    label = ask("Label", "")
    argv = ["web-capture", case_slug, url]
    if label:
        argv += ["--label", label]
    run_command(argv)


def action_identity_map() -> None:
    case_slug = ask_case_slug(must_exist=True)
    handle = ask("Pseudo / handle")
    use_all = ask_yes_no(
        f"Utiliser tous les sites publics connus ({len(IDENTITY_TEMPLATES)}) ?",
        True,
    )
    fetch = ask_yes_no("Faire aussi des requetes HTTP passives sur les profils ?", False)
    argv = ["identity-map", case_slug, handle]
    if not use_all:
        custom = ask(
            "Sites separes par des virgules",
            "github,x,instagram,tiktok,reddit,youtube,telegram,mastodon,linkedin",
        )
        argv += ["--platforms", custom]
    if fetch:
        argv.append("--fetch")
    run_command(argv)


def action_show_sites() -> None:
    lines = [f"{index:02d}. {name} -> {IDENTITY_TEMPLATES[name]}" for index, name in enumerate(IDENTITY_TEMPLATES, start=1)]
    print_section("PLATEFORMES DISPONIBLES", lines)


def action_media_inspect() -> None:
    case_slug = ask_case_slug(must_exist=True)
    path = ask("Chemin du media")
    run_command(["media-inspect", case_slug, path])


def action_archive() -> None:
    case_slug = ask_case_slug(must_exist=True)
    url = ask("URL a archiver")
    submit = ask_yes_no("Soumettre a Save Page Now ?", False)
    argv = ["archive", case_slug, url]
    if submit:
        argv.append("--submit")
    run_command(argv)


def action_breach_check() -> None:
    case_slug = ask_case_slug(must_exist=True)
    account = ask("Compte ou email a verifier")
    full = ask_yes_no("Demander la reponse complete si l'API l'autorise ?", False)
    argv = ["breach-check", case_slug, account]
    if full:
        argv.append("--full")
    run_command(argv)


def action_password_check() -> None:
    case_slug = ask_case_slug(must_exist=True)
    method = ask("Choix: 1=password, 2=sha1", "1")
    if method == "2":
        sha1_value = ask("SHA1 du mot de passe")
        run_command(["password-check", case_slug, "--password-sha1", sha1_value])
        return
    password = ask("Mot de passe a verifier")
    run_command(["password-check", case_slug, "--password", password])


def action_report_md() -> None:
    case_slug = ask_case_slug(must_exist=True)
    output = ask("Chemin de sortie optionnel", "")
    argv = ["report-md", case_slug]
    if output:
        argv += ["--output", output]
    run_command(argv)


def action_report_graph() -> None:
    case_slug = ask_case_slug(must_exist=True)
    output = ask("Chemin de sortie optionnel", "")
    argv = ["report-graph", case_slug]
    if output:
        argv += ["--output", output]
    run_command(argv)


def action_modules() -> None:
    run_command(["modules"])


def interactive_menu() -> int:
    actions = all_actions()

    while True:
        show_menu()
        try:
            choice = input("\nChoix > ").strip()
        except EOFError:
            return 0

        if choice == "00":
            clear_screen()
            print_line("Fermeture d'AtlasTrace.")
            return 0

        action = actions.get(choice)
        if action is None:
            print_error("Choix invalide.")
            pause()
            continue

        clear_screen()
        print_banner()
        try:
            action()
        except KeyboardInterrupt:
            print_error("\nAction annulee.")
        except Exception as exc:
            print_error(f"Erreur interactive: {exc}")
        pause()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print_banner()
        raise SystemExit(cli_main(sys.argv[1:]))
    raise SystemExit(interactive_menu())
