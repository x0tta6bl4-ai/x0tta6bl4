from aiohttp import web
import json

async def handle_peers(request):
    return web.json_response({"peers": ["test-peer-1", "test-peer-2"]})

async def handle_health(request):
    return web.json_response({"status": "ok"})

app = web.Application()
app.add_routes([
    web.get('/peers', handle_peers),
    web.get('/health', handle_health)
])

if __name__ == '__main__':
    print("🚀 DEBUG BRAIN STARTED ON 9091")
    web.run_app(app, port=9091)
