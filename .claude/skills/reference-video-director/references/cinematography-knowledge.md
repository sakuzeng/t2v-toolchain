# 参考视频导演知识库：景别、调度、运镜与剪辑

本文件服务于“已有视频 → 可核验导演分析”，不是通用电影史教程。使用顺序是：先观察画面，再查术语与证据，最后解释。术语不能反过来替代观察事实。

## 一、分析维度

每个镜头至少从以下维度分别记录：

1. **景别（Shot Scale）**：画面容纳多少人物与环境。
2. **机位角度（Shot Angle）**：平视、俯拍、仰拍、主观视点等。
3. **构图（Composition）**：主体位置、视觉重心、前中后景、留白、出入画方向。
4. **场面调度（Blocking / Staging）**：人物、肢体、道具与镜头如何在空间和时间中配合。
5. **镜头运动（Camera Movement）**：旋转、位移、变焦、手持运动或感知到的虚拟运动。
6. **剪辑（Editing）**：镜头边界、动作连续、视线连续、时间与空间关系。
7. **光线、色彩、焦点与焦距线索**：只记录画面证据，不凭单帧猜具体镜头毫米数。

这套拆分与 CineTechBench 的专家标注维度相容，但本项目另外强调人物调度、剪辑和可见性，以便反推生成提示词。

## 二、景别不是固定裁切公式

| 术语 | 常见画面范围 | 分析重点 |
|---|---|---|
| 大远景 `EWS/ELS` | 环境占主导，人物很小 | 空间、规模、方向和孤立感 |
| 全景／远景 `WS/LS` | 通常包含全身及环境 | 全身动作与场景关系 |
| 中景 `MS` | 常见为腰部以上 | 手臂动作、人物互动、环境信息平衡 |
| 中近景 `MCU` | 胸部以上 | 手势与面部同时可读 |
| 近景 `CU` | 面部或单一主体占主导 | 表情、反应和关键道具 |
| 特写 `ECU` | 眼睛、手、剑尖等局部 | 强调具体信息，不负责交代空间 |

景别应根据实际可见范围描述；“胸上近景”通常比只写 `Close-up` 更适合生成模型。景别变化可能来自镜头移动、人物移动、变焦或切镜，不能只看主体变大就下结论。

## 三、基础运镜及其可观察证据

| 运镜 | 物理／视觉定义 | 成片中的主要线索 | 常见误判 |
|---|---|---|---|
| 固定镜头 `Static Shot` | 相机位置和朝向基本不变 | 背景锚点稳定；只见人物或环境内部运动 | 防抖后的缓慢漂移不等于完全固定 |
| 横摇 `Pan` | 相机在固定位置水平旋转 | 画面内容整体横向经过；透视变化通常较弱 | 人物横穿固定画面；相机横移 `Truck` |
| 纵摇 `Tilt` | 相机在固定位置垂直旋转 | 构图沿垂直方向揭示新信息；视点位置基本不变 | 整机升降 `Pedestal`；人物自己上下移动 |
| 横移 `Truck` | 相机整体向左／右位移 | 前后景横向位移不同，可能出现视差 | 固定机位横摇 |
| 推／拉 `Dolly In/Out` | 相机整体靠近／远离主体 | 主体尺度与空间透视同时变化，前后景关系改变 | 单纯 `Zoom` 或人物向镜头走来 |
| 升／降 `Pedestal Up/Down` | 相机整体垂直位移 | 相机高度变化，前后景可能产生垂直视差 | 固定机位 `Tilt` |
| 跟随镜头 `Tracking Shot` | 镜头持续跟随移动主体 | 主体在构图中相对稳定，环境持续变化 | 仅在某一帧把主体放在中央 |
| 环绕／弧形 `Arc/Orbit` | 镜头绕主体改变观察角度 | 主体侧面比例与背景关系连续改变，具有明显视差 | 人物原地转身；纯横摇 |
| 升降／摇臂 `Crane/Jib` | 相机沿较大的空中路径移动 | 高度、角度和空间关系可能同时改变 | 仅凭“画面向上”猜测用了摇臂设备 |
| 变焦 `Zoom In/Out` | 相机不位移，只改变焦距 | 主体和背景同步放大／缩小，透视关系基本不变 | 推镜 `Dolly` |
| 滑动变焦 `Dolly Zoom` | 相机位移与反向变焦组合 | 主体尺度近似稳定，背景明显压缩或拉伸 | 普通快速推镜或后期数字缩放 |
| 手持 `Handheld` | 相机由操作者直接持握运动 | 不规则微抖、方向变化和人的步态节奏 | 人为添加的随机震动特效 |
| 滚转 `Roll` | 画面绕镜头光轴旋转 | 地平线和整个构图共同倾斜／旋转 | 人物或道具自身旋转 |

当二维证据不足以区别 `Tilt` 与 `Pedestal`、`Dolly` 与人物靠近时，使用中性描述，例如“快速向上重构图（fast upward reframing）”或“主体尺度逐渐增大”，并把具体设备运动列为不确定项。

## 四、如何判断“镜头跟着谁”

“跟随”是一种持续关系，不是主体曾经位于中央。分析时检查：

- 目标特征在多个时间点的标准化 `(x, y)` 轨迹是否相对稳定。
- 镜头响应是在目标动作之前、同时还是之后启动。
- 目标是否在整个运镜区间持续可见。
- 背景是否以与相机运动一致的方式变化。
- 运镜最后是否落在该动作所揭示的对象上。

可分为三档：

- **屏幕锁定 `screen-locked`**：目标位置近似不变，证据充分时才使用。
- **宽松跟随 `loose tracking`**：目标有可见漂移，但构图持续围绕它调整。
- **动作与运镜配合 `coordinated action and reframing`**：动作参与视觉过渡，但不是镜头的固定跟踪点。

## 五、人物调度与镜头的关系

把动作拆成“准备 → 发展 → 落点”，并记录每一阶段在画面中的可见性：

- **准备（Anticipation）**：垂手、蓄力、转头、重心变化等，使后续动作有来源。
- **发展（Development）**：手臂路径、身体移动或道具轨迹清楚展开。
- **落点（Resolution）**：动作停在能够传递信息或情绪的构图上。

如果生成结果只有最终姿势而缺少准备和发展，应判断为动作链被压缩，不应误判为“末帧命中所以通过”。镜头可以领先动作、响应动作或反向揭示动作，但必须如实记录发生顺序。

## 六、常用剪辑关系

| 剪辑关系 | 证据 | 提示词含义 |
|---|---|---|
| 硬切 `Hard Cut` | 相邻帧的视点、背景或时间突然不连续 | 明确写切点与新镜头信息 |
| 跳切 `Jump Cut` | 同一构图或动作中删除了一段时间，形成可见跳跃 | 不应误写成普通连续动作 |
| 动作匹配 `Match on Action` | 切前动作在切后由另一视点延续 | 两镜都写清动作接续状态 |
| 视线匹配 `Eyeline Match` | 先拍观看者，再切到其所看对象 | 写清观看方向与被看对象 |
| 叠化 `Dissolve` | 两幅画面短暂重叠、一幅淡出另一幅淡入 | 只有原片确实存在才使用 |
| 擦除／遮挡 `Wipe/Occlusion` | 前景穿过画面并覆盖边界 | 写清遮挡物、覆盖方向和新画面出现时机 |
| 连续重构图 `Continuous Reframing` | 无切镜，构图在同一连续运动中改变 | 不拆成多个 Shot；写起点、路径和落点 |

动作匹配剪辑可能在观看时显得“连续”，但它仍是切镜；反过来，scene score 在高速运动中给出的高值也不一定代表切镜。必须检查边界前后的密集帧。

## 七、导演分析输出规则

每个结论按以下顺序写：

1. **可观察事实**：时间码、主体位置、尺度、背景变化、动作阶段。
2. **支持的解释**：最符合证据的运镜／剪辑关系。
3. **可信替代项**：二维画面仍不能排除的解释。
4. **叙事作用**：揭示、跟随、强调、连接动作或改变情绪距离。
5. **模型指令**：只保留生成模型真正需要执行的关系。

不要把某种运镜的常见情绪效果写成固定规律。慢推可能制造亲密、压迫或信息强调，实际含义必须由人物表演、构图和上下镜共同决定。

## 八、H3 提示词适配

- 写“运镜类型 + 构图变化 + 速度／幅度 + 落点”，不要只堆术语。
- 能确定物理机制时使用 `Tilt Up`、`Dolly In` 等；不能确定时使用 `upward reframing`、`subject grows larger in frame` 等最低必要描述。
- 动作阶段必须按播放顺序写，尤其是手、手臂和道具的准备与落点。
- 明确实际切点；同一连续镜头内不要人为拆 Shot。
- 数字坐标、焦距或镜头速度只有在经过测量且对验收必要时才写。
- 运镜描述不能与 Depth／Pose／参考视频的结构控制相冲突。

## 九、资料来源与使用边界

本知识库对下列资料进行中文归纳，没有复制其整篇内容：

- Columbia University Film Language Glossary：镜头、场面调度、镜头运动和剪辑术语。<https://filmglossary.ccnmtl.columbia.edu/term/>
- Columbia Camera Movement：物理运动与感知／虚拟镜头运动的区分。<https://filmglossary.ccnmtl.columbia.edu/term/camera-movement/>
- 香港教育局《Resource Materials on the Learning and Teaching of Film》：Pan、Tilt、Dolly/Tracking、Pedestal、Crane、Zoom 的物理区别及透视线索。<https://edb.gov.hk/attachment/en/curriculum-development/kla/eng-edu/references-resources/Resource%20Materials%20on%20Learning%20and%20Teaching%20of%20Film.pdf>
- Adobe Tracking Shot：Tracking Shot 与 Dolly 装置概念的区别。<https://www.adobe.com/creativecloud/video/production/cinematography/camera-shots-and-angles/tracking-shot.html>
- Adobe Dolly Zoom：主体尺度稳定、背景透视拉伸／压缩的识别特征。<https://www.adobe.com/creativecloud/video/production/cinematography/camera-shots-and-angles/dolly-zoom-shot.html>
- Adobe Sequence Shot：动作匹配剪辑与连续性。<https://www.adobe.com/creativecloud/video/production/cinematography/camera-shots-and-angles/sequence-shot.html>
- StudioBinder Shot Sizes：景别、构图、调度和连续性的关系。<https://www.studiobinder.com/blog/types-of-camera-shots-sizes-in-film/>
- CineTechBench：面向多模态模型的七类电影摄影分析维度。<https://arxiv.org/abs/2505.15145>
