import warnings
warnings.filterwarnings("ignore", message=".*non-checked-in connection.*")
warnings.filterwarnings("ignore", message=".*garbage collector.*")
try:
    from sqlalchemy.exc import SAWarning
    warnings.filterwarnings("ignore", category=SAWarning)
except ImportError:
    pass

import click
from .commands.upload import cmd as upload_cmd
from .commands.dashboard import cmd as dashboard_cmd
from .commands.insights import cmd as insights_cmd
from .commands.learn import cmd as learn_cmd
from .commands.report import cmd as report_cmd


@click.group()
def cli():
    """✂  Cut the Fat — Persönliche Finanzanalyse"""
    pass


cli.add_command(upload_cmd, "upload")
cli.add_command(dashboard_cmd, "dashboard")
cli.add_command(insights_cmd, "insights")
cli.add_command(learn_cmd, "learn")
cli.add_command(report_cmd, "report")

if __name__ == "__main__":
    cli()
