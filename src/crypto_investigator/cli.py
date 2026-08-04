from pathlib import Path
import shutil

import typer

from crypto_investigator.config import load_config
from crypto_investigator.detection.identifier import detect_identifier
from crypto_investigator.exceptions import ConfigurationError, InvalidIdentifierError

app = typer.Typer(help="ChainSherlock: local-first blockchain transaction investigation toolkit.")


@app.command()
def detect(value: str = typer.Argument(..., help="Address or transaction hash to identify.")) -> None:
    """Detect the chain and type of an identifier."""
    try:
        identifier = detect_identifier(value)
    except InvalidIdentifierError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(identifier.model_dump_json(indent=2))


@app.command()
def providers(config: Path = typer.Option(Path("config/default.yaml"), exists=True)) -> None:
    """Show configured provider priority."""
    try:
        settings = load_config(config)
    except ConfigurationError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    for chain, provider in settings.providers:
        fallback = f" (fallback: {', '.join(provider.fallback)})" if provider.fallback else ""
        typer.echo(f"{chain}: {provider.primary}{fallback}")


@app.command("clear-cache")
def clear_cache(cache_dir: Path = typer.Option(Path("data/cache"))) -> None:
    """Remove locally cached provider responses."""
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        typer.echo(f"Cache cleared: {cache_dir}")
    else:
        typer.echo("Cache is already empty.")


if __name__ == "__main__":
    app()
