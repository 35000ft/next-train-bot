from datetime import datetime


def estimate_page_by_time(_time: datetime, max_page: int,
                          ratios: tuple = (0.02352, 0.270588, 0.2823529, 0.2823529, 0.1411764),
                          day_offset: int = 0) -> int:
    """
    根据分段航班数量比例预测分页页码。

    参数：
      _time: 当前时间（datetime 对象），用0点为起始时间
      max_page: 最大页码
      ratios: 长度为5的列表 [p1, p2, p3, p4, p5]，各代表各时段航班比例，且和为1.

    返回：
      预测得到的页码，整数值，范围在 1 到 max_page 之间。
    """
    # 定义各时间段的边界（分钟），以0点计时
    # 0-6 6-10 10-15 15-20 20-24
    boundaries = [0, 360, 600, 900, 1200, 1440]  # 0,6,10,15,20,24小时对应的分钟

    # 将当前时间转换为从0点开始的分钟数
    t = _time.hour * 60 + _time.minute + _time.second / 60.0 + day_offset * 1440

    # 计算累积比例
    cumulative = 0.0
    # 遍历各段：若 t 落在该段内，则在该段内按线性比例插值
    for i in range(5):
        lower = boundaries[i]
        upper = boundaries[i + 1]
        if t < upper:
            # 计算在本时段内占比
            fraction_in_segment = (t - lower) / (upper - lower)
            cumulative += fraction_in_segment * ratios[i]
            break
        else:
            # t 大于该段上界，累加整个段的比例
            cumulative += ratios[i]

    # 将累积比例映射到页码上
    # 页码 = int(累计比例 * max_page) + 1, 并确保不超过 [1, max_page]
    page = int(cumulative * max_page) + 1
    page = max(1, min(page, max_page))
    return page


# 示例使用：
if __name__ == "__main__":
    # 举例：假设你计算的比例如下（示例数据，请替换为你实际得到的值）：
    ratios = (0.02352, 0.270588, 0.2823529, 0.2823529, 0.1411764)
    max_page = 43  # 例如总页数为100

    # 当前时间示例：比如 2025-04-14 09:30:00
    current_time = datetime(2025, 4, 14, 0, 15, 0)
    predicted_page = estimate_page_by_time(current_time, max_page, ratios, day_offset=1)
    print("预测页码为:", predicted_page)
