from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import typer

from .api import create_app
from .converter import convert_workbook, read_workbook
from .database import validate_database
from .desktop import run_desktop
from .engine import Catalog, Planner, load_plan
from .errors import PlannerError
from .schemas import OutputRequest, PlanRequest

app = typer.Typer(help="Portable production planning backend.", no_args_is_help=True)
db_app = typer.Typer(help="Build and validate recipe databases.")
catalog_app = typer.Typer(help="Inspect a recipe catalog.")
plan_app = typer.Typer(help="Compute and inspect production plans.")
app.add_typer(db_app, name="db")
app.add_typer(catalog_app, name="catalog")
app.add_typer(plan_app, name="plan")


def _fail(exc: Exception) -> None:
    typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


@db_app.command("build")
def db_build(
    input_file: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    output_file: Path = typer.Option(..., "--output", dir_okay=False),
    force: bool = typer.Option(False, "--force", help="Replace an existing output file."),
):
    try:
        convert_workbook(input_file, output_file, force)
        typer.echo(str(output_file.resolve()))
    except PlannerError as exc:
        _fail(exc)


@db_app.command("validate")
def db_validate(database: Path = typer.Option(..., "--database", exists=True, dir_okay=False)):
    try:
        validate_database(database)
        typer.echo("Database is valid.")
    except PlannerError as exc:
        _fail(exc)


@db_app.command("check-workbook")
def workbook_validate(input_file: Path = typer.Option(..., "--input", exists=True, dir_okay=False)):
    try:
        read_workbook(input_file)
        typer.echo("Workbook is valid.")
    except PlannerError as exc:
        _fail(exc)


@catalog_app.command("search")
def catalog_search(
    database: Path = typer.Option(..., "--database", exists=True, dir_okay=False),
    query: str = typer.Argument(""),
    producible: bool | None = typer.Option(None, "--producible/--raw"),
    as_json: bool = typer.Option(False, "--json"),
):
    try:
        rows = Catalog(database).item_rows(query, producible)
        if as_json:
            typer.echo(json.dumps(rows, indent=2))
        else:
            for row in rows:
                typer.echo(f"{row['item_key']:<24} {row['kind']:<10} {row['name']}")
    except PlannerError as exc:
        _fail(exc)


def _parse_output(specification: str) -> OutputRequest:
    try:
        item_part, *priority_part = specification.split("@", 1)
        item_key, quantity = item_part.split("=", 1)
        priority = int(priority_part[0]) if priority_part else 1
        return OutputRequest(item_key=item_key.strip(), quantity=Decimal(quantity), priority=priority)
    except Exception as exc:
        raise typer.BadParameter("output must use ITEM=QUANTITY or ITEM=QUANTITY@PRIORITY") from exc


def _parse_override(specification: str) -> tuple[str, int]:
    try:
        station, count = specification.split("=", 1)
        return station.strip(), int(count)
    except Exception as exc:
        raise typer.BadParameter("station override must use STATION=COUNT") from exc


@plan_app.command("create")
def plan_create(
    database: Path = typer.Option(..., "--database", exists=True, dir_okay=False),
    output: list[str] = typer.Option(..., "--output", help="ITEM=QUANTITY[@PRIORITY]; repeat as needed."),
    profile: str = typer.Option("hay_day_default", "--profile"),
    station: list[str] = typer.Option([], "--station", help="STATION=COUNT; repeat as needed."),
    save: Path | None = typer.Option(None, "--save", dir_okay=False),
):
    try:
        request = PlanRequest(
            outputs=[_parse_output(value) for value in output],
            capacity_profile=profile,
            station_overrides=dict(_parse_override(value) for value in station),
        )
        document = Planner(Catalog(database)).compute(request)
        payload = document.model_dump_json(indent=2)
        if save:
            save.parent.mkdir(parents=True, exist_ok=True)
            save.write_text(payload + "\n", encoding="utf-8")
            typer.echo(str(save.resolve()))
        else:
            typer.echo(payload)
    except (PlannerError, ValueError) as exc:
        _fail(exc)


@plan_app.command("inspect")
def plan_inspect(plan_file: Path = typer.Argument(..., exists=True, dir_okay=False), as_json: bool = typer.Option(False, "--json")):
    try:
        document = load_plan(plan_file)
        if as_json:
            typer.echo(document.model_dump_json(indent=2))
            return
        typer.echo(f"Overall completion: {document.overall_completion_seconds} seconds")
        typer.echo(f"Raw material lines: {len(document.bom)}")
        typer.echo(f"Production jobs: {len(document.jobs)}")
        for output in document.outputs:
            typer.echo(f"- {output['name']}: {output['quantity']} complete at {output['completion_seconds']}s")
        for warning in document.warnings:
            typer.secho(f"Warning: {warning}", fg=typer.colors.YELLOW)
    except PlannerError as exc:
        _fail(exc)


@app.command("serve")
def serve(
    database: Path | None = typer.Option(None, "--database", exists=True, dir_okay=False),
    saved_plan: Path | None = typer.Option(None, "--plan", exists=True, dir_okay=False),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
):
    if database is not None and saved_plan is not None:
        raise typer.BadParameter("choose at most one of --database or --plan")
    import uvicorn
    uvicorn.run(create_app(database, saved_plan), host=host, port=port)


@app.command("desktop")
def desktop(
    database: Path | None = typer.Option(None, "--database", exists=True, dir_okay=False),
    saved_plan: Path | None = typer.Option(None, "--plan", exists=True, dir_okay=False),
    debug: bool = typer.Option(False, "--debug", help="Open the desktop web inspector."),
):
    """Run the planner in a contained desktop window."""
    if database is not None and saved_plan is not None:
        raise typer.BadParameter("choose at most one of --database or --plan")
    try:
        run_desktop(database=database, plan=saved_plan, debug=debug)
    except PlannerError as exc:
        _fail(exc)


if __name__ == "__main__":
    app()
