import click
from paste.translogger import TransLogger
from waitress import serve

from catalog_searcher import __version__
from catalog_searcher.app import app


@click.command()
@click.option(
    '-l', '--listen',
    metavar='[HOST]:PORT',
    help='Port (and optional host) to listen on. Defaults to "0.0.0.0:5000".',
    default='0.0.0.0:5000',
)
@click.option(
    '-t', '--threads',
    help='Maximum number of threads to use. Defaults to 10.',
    default=10,
)
@click.version_option(__version__, '-V', '--version')
def run(listen, threads):
    """Run the catalog searcher web app using the waitress WSGI server"""
    serve(TransLogger(app, setup_console_handler=True), listen=listen, threads=threads)
