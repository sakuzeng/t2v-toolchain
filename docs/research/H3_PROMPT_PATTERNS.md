# MiniMax H3 好 prompt 长什么样：官方范例与社区经验（2026-09-07）

> 问题：C001A 连续三版 prompt 都没让模型做出参考片的动作过程，用户要求先看别人效果好的 H3 prompt 是怎么写的，再决定怎么改。本文只记结论和可核对的原文摘录。

## 一、官方范例（模型卡 README 与 base/ref 指南，共 8 个完整范例）

**结构**：base 模式三段（`integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music`）；全参考模式六段。每个范例 200–500 词，句子长、名词具体、动词连续。

**时间怎么写**：时间戳只出现在切镜行 `[Shot 2] At 00:04.500, the camera cuts to …`。单镜内部一律用时间短语推进，官方 I2VA 拉面范例（8 秒静止长镜）原文用的是：

- "Early in the clip, the thick, white steam … immediately intensifies"
- "As the clip progresses into the middle seconds, the camera maintains its static position while the focus begins a deliberate, smooth shift deeper into the room"
- "With the focus now firmly locked on the background, …"
- "Throughout the remainder of the clip, the family continues …"

即：开头 / 中段 / 状态达成后 / 余下时间，四个时间锚点撑起一个 8 秒镜头，没有一个数字。

**动作怎么写**：官方 T2VA 星舰范例把物理反应写成因果链——"a blinding white flash floods through the window … The sheer spatial force violently jolts the bridge, causing the captain … to stagger slightly forward, her shoulders tensing as she visibly braces herself … As the intense white light fades abruptly, … her jaw clenches, and she slowly closes her eyes"。每个动作都有触发原因和身体部位。

**运镜**：固定句式 `The camera <类型> with <幅度> at <速度> as <主体动作>`，写进动作句里，不另起标签。

**否定句**：8 个官方范例里一句都没有。

## 二、社区指南的共识（Krea、EvoLink、Kapwing、cdance、inreels、siray、morphic 中文库）

| 共识 | 出处 | 对本项目的含义 |
|---|---|---|
| **一个镜头一个主动作**，镜头 2–5 秒；复杂序列拆成分时段的镜头，每拍 ≤2–3 秒且只含一个事件 | inreels、siray、EvoLink 的 11 拍猎手范例（15 秒 11 拍，每拍"exactly one event"） | C001A 在 3 秒里塞了落水、甩镜、手部剑指三个主动作，超过密度上限；模型压缩或跳过其中的动作是可预期的 |
| **一个镜头一条相机路径**；"随机切镜"的根因是多个相机动作/场景变化竞争 | cdance 故障表 | 我们的 v009 想让模型在甩镜里切，反而不被执行 |
| **画面断裂的修法是写出中间姿态**："Describe intermediate pose, object, and camera changes" | cdance 故障表 "Disconnected frames" | 手从髋侧到剑指、脚从悬空到沉水，都要写出中间那一两个姿态，而不是起点和终点 |
| 动作写成**动词链 + 环境反应 + 跟随相机** | cdance 特技范例（下文全文） | 我们的落水段形容词多、动词少 |
| 主体动作、相机动作、切镜**分开写**，别把三者揉进一个"dynamic tracking shot" | Kapwing | v007–v009 的甩镜段把三者写在一起 |
| 时间码：社区 brief 常用 `[0-3s]` 分段，morphic 中文库按"0至4秒 / 4至10秒"写，用来绑动作和音效 | Krea、Kapwing、morphic | 分段时间码是社区习惯，不是官方语法；对无音频、有控制片的镜头意义不大 |
| 否定句**少而短**，放在结尾，只列会毁片的项（"no text, no logos, no extra people"），或按 siray 的四项（impossible physics, extra limbs…） | Krea、siray | 我们的 v007–v009 每段三四个 never，属于反面 |
| 参考图**只定义一次身份**，之后靠一致性规则引用，不重复描述静态特征 | siray | 我们的 subject_definitions 已经这样做，正文不必再复述服装 |

**cdance 的特技范例全文**（最接近我们落水段需要的写法）：

> Live-action full-body shot in an empty warehouse. A stunt performer runs toward a low wooden barrier, plants both feet, clears it, lands with bent knees, rolls over the right shoulder, and rises into a run. Dust lifts on impact and settles behind him. A stabilized handheld camera follows from three meters back without overtaking him. Hard side light through tall windows. One continuous shot with footsteps, clothing movement, the landing impact, and no music.

七个动词把一个完整动作链写完，环境反应一句，相机一句，光一句，声音一句。

## 三、对照我们的 prompt

| 维度 | 官方/社区 | v007–v009 | v010 |
|---|---|---|---|
| 镜头内时间 | 时间短语 | 12 个 `At 00:0x` | 时间短语 ✓ |
| 否定句 | 0 或结尾 1 句 | 每段 3–4 句 never | 0 ✓ |
| 动作写法 | 动词链 + 中间姿态 + 环境反应 | 状态描述 + 禁止项 | 有中间姿态，但形容词偏多 |
| 密度 | 一镜一主动作 | 一镜三主动作 | 一镜三主动作（未变） |
| 相机 | 一镜一路径 | 一镜两段路径（快摇 + 慢升） | 同左 |

结论：v010 的写法已经对齐官方风格；剩下的问题不是措辞，而是**密度**——3 秒里三个主动作、两段相机路径，超过了这个模型在社区经验里的可靠上限。这与三次同 seed 产物几乎相同、且都省略中间动作的实测一致。

## 四、下一步建议（按代价）

1. **降密度而不改内容**：按 5 秒（121 帧）生成同一段内容，控制片按 1.67 倍重采样，prompt 用时间短语把三个动作分到"开头 / 中段 / 末段"，出片后加速 1.67 倍回到 3 秒。每个主动作得到约 1.7 秒，符合"一镜一主动作 2–5 秒"的经验；声画已分离，加速无音频问题。
2. 换 seed 一次（¥0.28），排除 seed 因素。
3. 若仍失败，走关键帧锚点（静帧 + AddGuide）。

## 来源
- 官方模型卡与范例：https://huggingface.co/MiniMaxAI/MiniMax-H3 ；官方写作 skill：https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/SKILL.md ；I2VA 系统提示词讨论：https://huggingface.co/MiniMaxAI/MiniMax-H3/discussions/47
- 社区指南：https://www.krea.ai/blog/10-best-minimax-h3-prompts-for-ai-film-influencers-and-omni-reference-2026 ；https://evolink.ai/minimax-h3-prompts ；https://www.kapwing.com/resources/how-to-prompt-minimax-h3-hailuo-3-0-a-guide-for-ai-video-creators/ ；https://cdance.ai/blog/minimax-h3-prompt-guide ；https://www.inreels.ai/blog/minimax-h3-prompt-guide ；https://blog.siray.ai/minimax-h3-prompt-guide-motion-control/ ；https://morphic.com/zh/resources/how-to/minimax-h3-prompts
- 重写器与工具：https://huggingface.co/lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA ；https://github.com/1038lab/Comfyui-Minimax-H3-Promptor ；https://github.com/hyukudan/ComfyUI-MiniMax-H3-Prompt-Enhancer
