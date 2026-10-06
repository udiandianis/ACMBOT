from ..router import Reply


def register(router, services, settings):
    """注册本模块的命令、帮助、权限与参数检查。"""
    router.register('media.list', r'给我\s*看看', lambda event, match: Reply(services.media.list(), forward=True), '给我看看：合并转发可用关键词列表')
    router.register('media.random', r'来只\s*(.*)', lambda event, match: services.media.random(match[1], event.group_id), '来只关键词：随机发送一张图片、一段视频、音频或文字')
    router.register('media.clear', r'清空\s*(.*)', lambda event, match: services.media.request_clear(match[1], event), '清空关键词：仅指定管理员可操作，需要确认', guard=lambda event: event.mentions == (settings.bot_qq,))
    router.register('media.add', r'添加\s*(.*)', lambda event, match: services.media.add(match[1], event.reply_id),
                    '回复原消息后发送 添加关键词：保存内容并返回编号，如 bjg-12', guard=lambda event: event.reply_id is not None)
    router.register('media.delete', r'删除\s*(.*)', lambda event, match: services.media.request_delete(match[1], event),
                    '引用机器人发出的内容发送 @机器人 删除关键词，或 @机器人 删除关键词-编号：仅管理员可操作，需要确认', guard=lambda event: event.mentions == (settings.bot_qq,))
    router.register('media.confirm', r'确认(删除|清空)\s+(.+)', lambda event, match: services.media.confirm(match[1], match[2], event),
                    '@机器人 确认删除 关键词-编号：由发起人在原群于 60 秒内确认删除\n'
                    '@机器人 确认清空 关键词：由发起人在原群于 60 秒内确认清空', guard=lambda event: event.mentions == (settings.bot_qq,))
    router.register('media.cancel', r'取消删除', lambda event, match: services.media.cancel(event),
                    '@机器人 取消删除：取消自己在当前群的待确认操作', guard=lambda event: event.mentions == (settings.bot_qq,))
