import calendar
from datetime import datetime
from PIL import Image, ImageDraw
from src.paths import CHECKIN_DIRECTORY, IMAGE_RESOURCES
from src.fonts import draw_text


def get_png(event):
    """创建或更新用户当月签到图片，原子写入后返回文件路径。"""
    now = datetime.now()
    directory = CHECKIN_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    user_id = event['sender']['user_id']
    output_path = directory / f'{user_id}{now.year}{now.month}.png'
    month = calendar.monthcalendar(now.year, now.month)
    box_size, start_x, start_y = 50, 125, 130
    if output_path.exists():
        image = Image.open(output_path).convert('RGB')
    else:
        image = Image.new('RGB', (600, max(450, start_y + len(month) * box_size)), 'white')
        drawing = ImageDraw.Draw(image)
        draw_text(drawing, (10, 10), f'{now.year}年{now.month:02d}月', 24)
        draw_text(drawing, (10, 50), event['sender'].get('nickname', str(user_id)), 24)
        for column, weekday in enumerate(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')):
            draw_text(drawing, (start_x + column * box_size, start_y - 30), weekday, 24)
        background = Image.open(IMAGE_RESOURCES / 'day.png').convert('RGBA').resize((box_size, box_size))
        for week_number, week in enumerate(month):
            for weekday_number, day in enumerate(week):
                if day:
                    left = start_x + weekday_number * box_size
                    top = start_y + week_number * box_size
                    image.paste(background, (left, top))
                    draw_text(drawing, (left + 2, top + box_size - 12), str(day), 10)
    checkmark = Image.open(IMAGE_RESOURCES / 'tick.png').convert('RGBA').resize((60, 60))
    checkmark.putdata([(255, 255, 255, 0) if all(channel > 200 for channel in pixel[:3]) else pixel for pixel in checkmark.getdata()])
    for week_number, week in enumerate(month):
        if now.day in week:
            weekday_number = week.index(now.day)
            image.paste(checkmark, (start_x + weekday_number * box_size - 5, start_y + week_number * box_size - 5), checkmark)
            break
    temporary_path = output_path.with_suffix('.tmp.png')
    image.save(temporary_path)
    temporary_path.replace(output_path)
    return output_path
