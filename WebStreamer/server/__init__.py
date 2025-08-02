# WebStreamer/server/__init__.py

import logging
import aiohttp_jinja2
import jinja2
from aiohttp import web
from .stream_routes import routes as stream_routes
from .panel_routes import routes as panel_routes

logger = logging.getLogger("server")

def web_server(bot):
    logger.info("Initializing Web Server...")
    
    app = web.Application()

    # Store bot instance and auth token in the app context
    app['bot'] = bot
    app['admin_auth_token'] = None
    
    # Setup Jinja2 templates with async mode enabled
    aiohttp_jinja2.setup(
        app, 
        enable_async=True,  # This line fixes the error
        loader=jinja2.FileSystemLoader('WebStreamer/templates')
    )
    
    app.add_routes(stream_routes)
    app.add_routes(panel_routes)
    logger.info("Added stream and panel routes")
    
    return app