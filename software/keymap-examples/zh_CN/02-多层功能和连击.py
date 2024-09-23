# 如何配置键位图？（我以前叫它键值表）
# 注1：井号开头的都是注释，不影响功能
# 注2：缩进用Tab/制表符更省存储空间，这个文件里用的都是空格，每层缩进4个空格

# 准备工作，从lib导入模块
from lemon_keypad.keycode_helper import * # 导入键码，这样不用再重复手写数字了
from lemon_keypad import CompositeAction as Act # 导入复合按键工具，改名Act
from lemon_keypad import TapDance as TD # 导入连击按键工具，改名TD
from lemon_keypad import KeySequence as KS # 导入序列按键工具，改名KS
from lemon_keypad import KeyCombination as KC # 导入组合按键工具，改名KC

# 键位图是一个个存在字典（dict，用花括号）中的列表（list，用方括号）
# 键位图需定义所有按键的功能。如果不打算给某个按键分配功能，请填写一个“None”（不含引号）。

#=====     示例2 - 多层功能和连击     =====#
keymap = {
    # 默认层为0，不过也可以改成别的，需要额外配置
    0: [
        # 单击切换播放/暂停，按住可以激活自定义层
        Act(C_PLAY_PAUSE, layer='自定义'),

        # 没动作就写None
        None,
        None,

        # 只切层也是可以的
        Act(layer='文本输入'),

        # 鼠标右键
        M_RIGHT,

        # 切换到Ctrl层，同时按下左Ctrl键
        Act(hold=CONTROL, layer='Ctrl键'),  # 最后一个逗号可有可无
    ], # 注意分隔逗号

    # 层名也可以是字符串，但是要用双引号或单引号包裹
    '自定义': [
        # 注意，切换键位图层时，触发层切换的键不会在新的键位图层触发新功能
        # 想触发这个功能，需用另外一个键切换到这一层
        C_STOP,

        # 单击切换暂停，双击下一曲，三击上一曲，
        # 默认按键间隔不超过200毫秒，可以通过 tap_term_ms 调整
        # 没有备选按键的数量限制，可以写100个动作在里面，最后只会执行一个
        # 这个动作不能是复合按键Act。复合按键和连击动作互不兼容
        TD(C_PLAY_PAUSE, C_SCAN_NEXT_TRACK, C_SCAN_PREVIOUS_TRACK),
        # 例子：可以这样改按键间隔
        # TD(C_PLAY_PAUSE, C_SCAN_NEXT_TRACK, C_SCAN_PREVIOUS_TRACK, tap_term_ms=300),

        # 增加音量
        C_VOLUME_INCREMENT,

        # 切换静音
        C_MUTE,

        # 降低音量
        C_VOLUME_DECREMENT,

        # 短按切换上一曲，长按倒带
        Act(C_SCAN_PREVIOUS_TRACK, C_REWIND),
    ],

    '文本输入': [ # 若使用文本输入功能，之前按下的键会在软件层面全部松开，避免冲突

        # 实际上文本输入只是按下对应按键的符号，所以不能用键盘直接输入的符号也无法输入
        # 字符串太长可以分行录入，中间是空行或空格，没有逗号
        # 不过过分长的字符串（反正很长）会让系统崩溃
        # 想输入超长内容，有别的方法，需要用到自定义函数
        'Hello world! nihao shijie! '
        'zhe shi di 2 hang',
        
        # 反斜杠（\）能用来输入特殊符号
        # 回车：\n，制表符：\t，退格：\b，ESC：\x1b
        # 你会发现Backspace后面的冒号被后一个退格符号删掉了
        'Enter: \n, Tab \t, Backspace \b, Escape \x1b',

        # 当需要输入反斜杠（\）时，需要多一个反斜杠（\）来转义，保证实际是斜杠
        'ceshi yixia !@#$%^{}~`| \\',

        # 提示一下，用字符串输入功能也可以用来实现狂按某个按键很多次，不过也可以用后面的按键序列做

        None,
        None,
        None,
    ],

    'Ctrl键': [
        # 按键序列，先点击A再点击C
        # 结合之前切层时按下的Ctrl，变成了Ctrl+A，Ctrl+C
        KS(A, C),

        # 组合按键，按顺序依次按下SHIFT和ESCAPE，
        # 结合切层时按下的Ctrl，在Windows系统上是开启任务管理器的快捷键
        KC(SHIFT, ESCAPE),

        None, None, None, None,
    ]
}

# 想用鼠标键，直接引用鼠标按键即可
# 在keycode_helper.py中可以查到
# 左键，右键，中键，
M_LEFT
M_MIDDLE
M_RIGHT
