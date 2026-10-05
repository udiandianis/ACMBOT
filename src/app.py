import logging
from flask import Flask, jsonify, request
from .settings import get_settings
from .adapters.napcat import NapCatClient
from .commands import build_router
from .events import GroupMessage

logger = logging.getLogger(__name__)


def create_app(settings=None, client=None, services=None):
    """组装 HTTP 应用、配置、服务和路由；参数可注入以便测试。"""
    settings = settings or get_settings()
    client = client or NapCatClient(settings)
    if services is None:
        from .services.container import BotServices
        services = BotServices(settings, client)
    router = build_router(services, settings)
    app = Flask(__name__)
    app.extensions.update(bot_router=router, bot_services=services, bot_settings=settings)

    @app.get('/health')
    def health():
        """返回服务状态和已注册的命令数量，不调用外部接口。"""
        return jsonify(status='ok', commands=len(router.commands))

    @app.post('/')
    def webhook():
        """接收 OneBot 事件，执行群命令并发送响应；忽略自身消息。"""
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='JSON object required'), 400
        if data.get('notice_type') == 'group_increase':
            try:
                group, user = int(data['group_id']), int(data['user_id'])
            except (KeyError, ValueError, TypeError):
                return jsonify({})
            if group in settings.welcome_groups and user is not None:
                try:
                    client.send_group(group, [
                        {'type': 'at', 'data': {'qq': str(user)}},
                        {'type': 'text', 'data': {'text': settings.welcome_message}},
                    ])
                except Exception:
                    logger.exception('群欢迎消息发送失败')
            return jsonify({})
        event = GroupMessage.parse(data)
        if event is None or event.user_id == settings.bot_qq:
            return jsonify({})
        try:
            reply = router.dispatch(event)
        except ValueError as error:
            from .router import Reply
            reply = Reply(str(error))
        except Exception:
            logger.exception('Command failed in group=%s user=%s', event.group_id, event.user_id)
            from .router import Reply
            reply = Reply('处理失败，请稍后重试')
        if reply and reply.text:
            try:
                method = client.send_forward if reply.forward else client.send_group
                result = method(event.group_id, reply.text)
                if reply.on_sent:
                    reply.on_sent(result)
            except Exception:
                logger.exception('Reply delivery failed in group=%s', event.group_id)
        return jsonify({})

    return app
