# 可测量验收规格（acceptance）

"达到标准"必须先写成数字，再由 `scripts/check_acceptance.py` 对产物自动核对；人只裁决 `manual` 项和表格没覆盖的部分。

## 放哪里

- 每个镜头一份 JSON：`prompts/shots/<镜头>/acceptance_<版本或镜头>.json`，纳入 Git。
- prompt frontmatter 单行引用：`acceptance: acceptance_v006.json`（相对 prompt 所在目录）。仓库 `t2v.py` 的 frontmatter 解析器只认单行，不要写多行 YAML。
- 数值来自参考片的 `measure_tracks.py` 结果，容差写在每项 `note` 里。**先用参考片自身跑一遍规格，全部通过才算校准完成**；参考片都过不了的项是写错了，不是标准高。

## 结构

```json
{
  "shot": "c001a",
  "derived_from": "参考片路径与测量目录",
  "tracks": [{"label": "fingertip", "t": 2.0, "x": 0.50, "y": 0.30}],
  "criteria": [ {"id": "A1", "type": "...", "...": "...", "note": "为什么是这个数"} ]
}
```

`tracks` 是需要 LK 跟踪的播种点，产物和参考各自播种在同一相对时刻。

## 支持的 type

| type | 参数 | 判定 | 用途 |
|---|---|---|---|
| `no_cut_between` | `range:[a,b]` | 区间内无 `hard_cut_likely` | 一镜到底段 |
| `cut_within` | `range:[a,b]` | 区间内有硬切 | 复刻切点 |
| `motion_onset_within` | `range`, `factor`(默认3), `search_from` | 能量首次 ≥ factor×全片中值的时刻落在区间 | 转场/动作起始时机 |
| `motion_peak_within` | `range`, `search:[a,b]` | 搜索段内能量峰值时刻落在区间 | 甩镜最快时刻 |
| `high_motion_duration_min` | `window`, `min_seconds`, `factor`(默认2) | 窗口内能量 ≥ factor×中值的累计时长 | 模糊/大运动窗口不被压成跳变 |
| `hold_min` | `window`, `min_seconds` | 窗口内最长停顿 ≥ 阈值 | 参考片有定格 |
| `no_hold` | `window`, `max_seconds`(默认0.2) | 窗口内最长停顿 < 阈值 | 防"落地后站着等切" |
| `eye_dist_min_by` | `by`, `min` | 两眼间距（占画幅宽）首次 ≥ min 的时刻 ≤ by | 何时抵达近景 |
| `eye_dist_range_at` | `t`, `min`, `max`, `tol`(默认0.1) | t±tol 内眼距中值落在区间 | 近景景别稳定 |
| `person_visible_frac_min` | `window`, `min` | 窗口内人物检出率 | 主体持续在画 |
| `track_range_max` | `window`, `label`, `max` | 跟踪点覆盖 ≥0.5 且漂移 ≤ max | 真正的屏幕锁定 |
| `track_coverage_min` | `window`, `label`, `min` | 跟踪覆盖率 | 特征持续可见 |
| `energy_ratio_vs_ref_min` | `ref_window`, `min` | 产物（经时间映射）与参考同窗口能量均值之比 | 动作能量不缩水（需 `--ref-measure-dir`） |
| `roi_occupancy_quiet_until` | `roi:[x0,y0,x1,y1]`, `until`, `max_frac`(默认0.08), `dark_thr`(默认70) | 该时刻前 ROI 内暗像素占比峰值 < max_frac | 主体不得提前入画（亮背景上的深色主体/墨迹） |
| `roi_occupancy_onset_within` | `roi`, `range`, `min_frac`(默认0.10) | 暗像素占比首次 ≥ min_frac 的时刻落在区间 | 脚/手/道具何时进入某区域 |
| `roi_occupancy_at` | `roi`, `t`, `min`, `max`, `tol` | t±tol 内占比中值落在区间 | 某时刻主体已沉入/已离开该区域 |
| `roi_motion_onset_within` | `roi`, `range`, `factor`, `search_from` | ROI 帧差首次 ≥ factor×ROI 中值的时刻 | 局部动作起始 |
| `roi_quiet_until` | `roi`, `until`, `factor` | 该时刻前 ROI 帧差峰值 < factor×中值 | 局部静止（注意：静止的主体也"安静"，判入画用 occupancy） |
| `roi_energy_min` | `roi`, `window`, `min` | 窗口内 ROI 帧差均值 | 局部动作量下限 |
| `roi_energy_ratio_vs_ref_min` | `roi`, `ref_window`, `min` | 产物（经时间映射）与参考同窗口 ROI 帧差均值之比 | 局部动作（如脚触水→下沉→墨花）不缩水 |
| `manual` | `text` | 待人工 | 剑是否在左侧、眼神变化等测不了的 |

ROI 两种量的分工：**占比**答"在不在、什么时候到"，**帧差**答"动没动、动多少"。静止的脚帧差为零但占比很高，别用帧差判入画时机。

停顿定义：能量 ≤ 窗口峰值 20% 且持续 ≥0.2 s（`measure_tracks.py --hold-ratio`）。
眼距阈值参考：胸上近景约 0.10–0.14 W，中景约 0.03–0.05 W。

## 容差怎么定

- 时机类：参考值 ±0.10 s（H3 时间码本身是软约束，比这紧就是抽卡）。
- 时长类：参考值的 70%。
- 能量比：≥0.6（历史纯文字版只有参考的三分之一，0.6 已是明显进步；通过后再收紧）。
- 眼距：参考值 ±0.03 W。

## 跑法

```bash
workon text2video
# 校准：参考片自己必须全过
python .claude/skills/reference-video-director/scripts/check_acceptance.py \
  --video projects/<p>/references/clips/<shot>/reference.mp4 --spec <spec.json> --measure-dir <dir>/ref
# 产物：带时间映射（产物t:参考t）与参考测量目录
python .claude/skills/reference-video-director/scripts/check_acceptance.py \
  --video projects/<p>/runs/<shot>/<run>/picture.mp4 --spec <spec.json> \
  --measure-dir projects/<p>/runs/<shot>/<run>/qa/measure --ref-measure-dir <dir>/ref \
  --time-map 0:0,2.3:2.3,3.0417:2.875 --report projects/<p>/runs/<shot>/<run>/qa/acceptance.md
```

报告进 run capsule 的 `qa/`，与六审表并列；`review` 时先看它，再看片。

## 示例（c001a，已用参考片校准）

见 `projects/chiling-ink-sword/prompts/shots/c001a/acceptance_c001a.json`。
