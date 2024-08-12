import pandas as pd
import matplotlib.pyplot as plt
from pandas.plotting import table
import LuoguQuery
import NewcoderQuery
import CodeforcesQuery



def get_png():
    # 读取 Excel 文件
    df1 = pd.read_excel('check.xlsx')  # 要查询的 qq
    df2 = pd.read_excel('qqid.xlsx')
    df3 = pd.DataFrame(columns=['NAME', 'CF', 'LG', 'NK', 'ALL','RANK'])  # 用空的DataFrame代替

    data = {}
    qq_dic = {}
    lazy1 = []
    lazy2 = []
    for i in df1['qq']:
        dic = {'NAME': '', 'CF': '0/0', 'LG': '0/0', 'NK': '0/0', 'ALL': '0/0', 'RANK': '0'}
        ac = submit = 0
        idx1 = df1['qq'].to_list().index(i)
        idx2 = df2['qq'].to_list().index(i)
        dic['NAME'] = df1['name'][idx1]
        print(dic['NAME'])
        try:
            cfdata = CodeforcesQuery.get_data(df2['cf'][idx2])
            ac += cfdata['TodayAccept']
            submit += cfdata['TodaySubmit']
            dic['CF'] = f"{cfdata['TodayAccept']}/{cfdata['TodaySubmit']}"
        except:
            pass
        print("CF Using...")
        try:
            lgdata = LuoguQuery.get_data(df2['lg'][idx2])
            ac += lgdata['TodayAccept']
            submit += lgdata['TodaySubmit']
            dic['LG'] = f"{lgdata['TodayAccept']}/{lgdata['TodaySubmit']}"
        except:
            pass
        print("LG Using...")
        try:
            nkdata = NewcoderQuery.get_data(df2['nk'][idx2])
            ac += nkdata['TodayAccept']
            submit += nkdata['TodaySubmit']
            dic['NK'] = f"{nkdata['TodayAccept']}/{nkdata['TodaySubmit']}"
        except:
            pass
        print("NK Using...")
        dic['ALL'] = f"{ac}/{submit}"
        data[i] = dic
        qq_dic[i] = [ac, submit]
        if ac == 0:
            lazy1.append(dic['NAME'])
        if ac == submit == 0:
            lazy2.append(dic['NAME'])

    # 按照 ac 和 submit 排序
    solve = sorted(qq_dic.items(), key=lambda x: (x[1][0], x[1][1]), reverse=True)
    rank = 1
    for i in range(len(solve)):
        if i>0 and solve[i][0]!=solve[i-1][0] and solve[i][1]!=solve[i-1][1]:
            rank+=1
        data[solve[i][0]]['RANK'] = rank
        df3 = df3._append(data[solve[i][0]], ignore_index=True)


    # 设置字体以显示中文
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
    plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

    # 去除行索引和列索引
    df3.columns = df3.columns.to_series().apply(lambda x: str(x).strip())  # 去除列名中的空格
    df3.index = [''] * len(df3)  # 移除行索引

    # 计算适合的图形大小
    n_rows = len(df3)
    row_height = 0.6  # 每行的高度（单位：英寸）
    fig_height = n_rows * row_height
    fig_width = 15  # 固定宽度

    # 创建一个新的图形对象
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))  # 根据行数调整图形大小

    # 隐藏坐标轴
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.set_frame_on(False)

    # 创建表格并添加到图形中，不包含行索引和列索引
    tab = table(ax, df3, loc='center', cellLoc='center', colWidths=[0.1] * len(df3.columns))  # 调整列宽
    tab.auto_set_font_size(False)
    tab.set_fontsize(20)  # 字体大小增加
    tab.scale(1.6, 1.6)  # 比例放大

    # 标记lazy
    for key, cell in tab.get_celld().items():
        row, col = key
        if row > 0 and col == 0:  # 跳过标题行，只处理'NAME'列的内容
            if cell.get_text().get_text() in lazy1:
                cell.set_text_props(color='purple')
            if cell.get_text().get_text() in lazy2:
                cell.set_text_props(color='green')
    # 调整布局以减少多余空白
    plt.tight_layout(pad=0.5)  # 增加padding以避免重叠

    # 保存表格为图片
    output_image = 'solve.png'
    plt.savefig(output_image, bbox_inches='tight', pad_inches=0.1, dpi=300)  # 提高dpi提高分辨率

    print(f"表格已保存为 {output_image}")
