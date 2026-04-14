import click
from loguru import logger

from config import load_config
from db.connection import get_connection
from runner import run_all


@click.group()
def cli():
    pass


@cli.command()
@click.option("--target", "target_id", type=int, default=None,
              help="Scrape a single target by ID. Omit to run all enabled targets.")
def run(target_id):
    """Trigger a scrape run immediately."""
    config = load_config()
    run_all(config, target_id=target_id)


@cli.group()
def target():
    """Manage scrape targets."""
    pass


@target.command("add")
@click.option("--type", "target_type", required=True,
              type=click.Choice(["account", "search"]), help="Target type")
@click.option("--value", required=True, help="Username (no @) or search query")
def target_add(target_type, value):
    """Add a new scrape target."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO scrape_targets (type, value, enabled, created_at) VALUES (%s, %s, TRUE, NOW())",
            (target_type, value),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        cursor.close()
        conn.close()
    click.echo(f"Added target #{new_id}: [{target_type}] {value}")


@target.command("list")
def target_list():
    """List all scrape targets."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM scrape_targets ORDER BY target_id")
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    if not rows:
        click.echo("No targets configured.")
        return
    for row in rows:
        status = "enabled" if row["enabled"] else "disabled"
        click.echo(f"#{row['target_id']} [{row['type']}] {row['value']} ({status})")


@target.command("enable")
@click.argument("target_id", type=int)
def target_enable(target_id):
    """Enable a scrape target by ID."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE scrape_targets SET enabled = TRUE WHERE target_id = %s", (target_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    click.echo(f"Target #{target_id} enabled.")


@target.command("disable")
@click.argument("target_id", type=int)
def target_disable(target_id):
    """Disable a scrape target by ID."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE scrape_targets SET enabled = FALSE WHERE target_id = %s", (target_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    click.echo(f"Target #{target_id} disabled.")


@cli.command()
@click.option("--last", default=10, show_default=True, help="Number of recent runs to display")
def logs(last):
    """View recent scrape run logs."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT r.run_id, r.started_at, r.tweets_collected, r.status, r.error_message,
                   t.type, t.value
            FROM run_logs r
            JOIN scrape_targets t ON r.target_id = t.target_id
            ORDER BY r.run_id DESC
            LIMIT %s
            """,
            (last,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    if not rows:
        click.echo("No run logs found.")
        return
    for row in rows:
        icon = "✓" if row["status"] == "success" else "✗"
        click.echo(
            f"{icon} #{row['run_id']} [{row['type']}] {row['value']}"
            f" — {row['tweets_collected']} tweets — {row['started_at']}"
        )
        if row["error_message"]:
            click.echo(f"  Error: {row['error_message']}")


if __name__ == "__main__":
    cli()
