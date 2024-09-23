# 准备工作，从lib导入模块
from lemon_keypad import LemonKeypad

# 自定义函数支持普通函数和异步函数，写好后把函数直接当键值填进键位图里需要的位置就好
# 需要注意，自定义函数执行后，键盘内部状态会重置为所有键都没有按下的状态。
# 也就是说，用组合键触发自定义函数后，组合键状态不会保留

# 来整一个简易水平仪程序，异步版本
import asyncio
from ulab import numpy as np

async def level_gauge(dev: LemonKeypad):  # 第一个参数是LemonKeyboard对象，名称无所谓，目前只支持这一个参数

    # 设备有自带一个姿态传感器
    imu = dev.imu
    
    # 还有RGB彩灯
    pixels = dev.pixels
    
    # 要是上面两个设备有一个不存在，咱就不玩了
    if imu is None or pixels is None:
        return
    
    # 把按键事件队列拿过来方便玩
    event_queue = dev.key_scanner.events

    # 假设所有灯按环形排列，一圈，顺时针方向
    # 圆心在(0,0)，半径1，第一个按键坐标是(0,1)
    led_positions = np.array(
        [
            (np.cos((i * 360/pixels.n + 90) / 360 * 6.283), np.sin((i * 360/pixels.n + 90) / 360 * 6.283)) for i in range(pixels.n, 0, -1)
        ]
    )

    # 其它准备工作
    red = np.array((0x40, 0, 0)) # 红色
    green = np.array((0, 0x40, 0)) # 绿色
    blue = np.array((0, 0, 0x40)) # 蓝色

    # 开始不断循环
    while True:
        # 因为是异步函数，多组程序共享资源，最好让别的程序也有机会运行一下
        # 放开头可以保证每次循环都执行
        await asyncio.sleep(0)

        # 尝试获取一个新事件
        new_event = event_queue.get()
        if new_event is not None and new_event.pressed:
            # 这样做到按任意键退出
            pixels.fill((0, 0, 0)) # 清空led
            break

        # 这就是主体程序了
        x1, y1, z1 = imu.acceleration
        x2, y2, z2 = imu.gyro
        print("Acc: X:%6.2f, Y: %6.2f, Z: %6.2f m/s^2; G: X:%6.2f, Y: %6.2f, Z: %6.2f radians/s" % (x1, y1, z1, x2, y2, z2))
        platform_vector = np.array((x1, y1))
        length = np.linalg.norm(platform_vector)
        if length < 0.27: # 平了，绿灯
            pixels.fill(green.tolist())
            continue
        unit_vector = platform_vector / length
        factors = np.dot(led_positions, unit_vector)
        factors = np.array([factors]).transpose()
        colors = factors * red + (1 - factors) * blue
        pixels[:] = colors.tolist()

# 塞进键位图
keymap = {
    0: [
        level_gauge,
        None,
        None,
        None,
        None,
        None,
    ],
}