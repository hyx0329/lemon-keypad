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

#=====    示例1 - 常用多媒体切换功能    =====#
keymap = { # 这是个字典，键可以是数字和字符串，键后面跟冒号，与值分隔开
    # 键位图层，名称为“0”，默认的默认层是0，不过也可以改
    0: [ # 这是个列表，用方括号
        # 共6个键，USB对应位置为第一个按键，按顺时针顺序依次填写按键功能
        # 用逗号隔开，空格空行都可以删除

        # 切换播放/暂停，这是单个键
        C_PLAY_PAUSE,

        # 短按切换下一曲，长按快进
        Act(C_SCAN_NEXT_TRACK, C_FAST_FORWARD),

        # 增加音量
        C_VOLUME_INCREMENT,

        # 切换静音, 但是双击或单击一次再按住会触发A，三击或双击依次再按住会触发B，以此类推，连击满后自动执行最后一个
        C_MUTE,

        # 降低音量
        C_VOLUME_DECREMENT,

        # 短按切换上一曲，长按倒带
        Act(C_SCAN_PREVIOUS_TRACK, C_REWIND),
    ],
}

### 后面的代码没用，只是说明，想用现成只需复制前面的代码

# 上面键位图中Act可以用来标记很复杂的功能，可以实现单击、长按、超长按、层切换功能
# Act(CompositeAction)的全部参数如下，等号后面的值为默认值，None代表默认没动作：
Act(
    # 单击动作
    tap = None,

    # 长按动作
    hold = None, # 长按动作

    # 长按时切换的键位图层
    layer = None,

    # 超级长按动作
    long_hold = None,

    # 单击超时时间（毫秒），如果配置了hold或long_hold，则长按超过这个时间后将不触发单击动作
    tap_term_ms = 200,

    # 长按超时时间（毫秒），如果配置了long_hold，则在长按超过这个时间后将不触发长按动作
    # 也就是说，如果配置了long_hold，只有在时间内松开或者按下其它按键才会触发长按动作（hold）
    hold_term_ms = 2000,

    # 超级长按开始时间（毫秒），如果配置了long_hold，则在长按时间达到这个长度后就会激活超级长按动作
    # 若在长按时间落在 hold_term_ms 和 long_hold_start_ms之间时松开按键，那么什么动作都不会触发
    long_hold_start_ms = 5000,

    # 是否在有新按键按下时优先触发单击动作，这个只在配置了layer和hold时有效果
    tap_preferred = False,
)
### Act 示例

# 单击切换暂停，超级长按停止。因为跳过了几个参数，后面的参数需要加参数名
Act(C_PLAY_PAUSE, long_hold=C_STOP)

# 单击切换暂停，长按快进
Act(C_PLAY_PAUSE, C_FAST_FORWARD)