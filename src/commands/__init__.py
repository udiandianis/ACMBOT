from . import accounts, general, media, training, duels


def build_router(services, settings):
    """创建路由并注册所有功能模块的命令。"""
    from ..router import Router
    router = Router()
    for module in (general, accounts, media, training, duels):
        module.register(router, services, settings)
    return router
