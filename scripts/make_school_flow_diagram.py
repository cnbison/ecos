"""生成面向学校的「一道题的一生」正式流程图（docs/for-schools-flow.png）。

对应 docs/for-schools.md §三 的六步流程。一次性文档资产生成脚本，可复跑。
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

# 中文字体（macOS 简体优先）
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "PingFang SC", "STHeiti", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

# ---- 配色（打印友好、克制） ----
INK = "#1F2A37"          # 主文字
SUB = "#5A6B7B"          # 说明文字
BOX_FACE = "#F2F7FC"     # 步骤框底色
BOX_EDGE = "#3A6EA5"     # 步骤框边框
BADGE = "#2C5F8A"        # 编号徽章
LOOP = "#6B8E4E"         # 循环回馈（灰绿）
ACCENT_DIAG = "#0E7C7B"  # 诊断 AI（青绿）
ACCENT_COACH = "#C07000"  # 教练 AI（橙）

# ---- 六步内容 ----
STEPS = [
    ("学生做题", "题库里每一道题都带着「处方单」：标出它考察哪个维度、对应哪个认知层次"),
    ("学生自评信心", "揭晓对错之前，先问一句「我有几成把握」——把「真会」和「蒙对」分开"),
    ("AI 判题", "不只判对错，还理解作答过程：错在哪里、为什么错"),
    ("更新认知状态", "五个维度各自更新，并记录判断依据——每一句判断都可追溯"),
    ("决定怎么帮", "根据最新状态决定：何时复习、给多少提示、下一题出多难"),
    ("三端呈现", "老师看诊断与证据 · 家长看成长与建议 · 学生看进步与下一步"),
]

# ---- 画布与坐标 ----
FIG_W = 9.0
BOX_X0, BOX_X1 = 1.35, 7.75          # 步骤框左右
BOX_W = BOX_X1 - BOX_X0
BOX_H = 1.5
GAP = 0.72                            # 框间距（留箭头）
TOP = 12.6                            # 第一框顶部 y
TITLE_Y = 13.4                        # 大标题 y
LOOP_X = 0.55                         # 左侧回馈线 x

fig, ax = plt.subplots(figsize=(FIG_W, 13.8))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, 14.4)
ax.axis("off")

# 大标题 + 副标题
ax.text(FIG_W / 2, TITLE_Y, "一道题的一生",
        ha="center", va="center", fontsize=26, fontweight="bold", color=INK)
ax.text(FIG_W / 2, TITLE_Y - 0.5, "从学生做完一道题，到老师与家长看到「该怎么办」——六步看得见",
        ha="center", va="center", fontsize=12.5, color=SUB)

y = TOP
bottoms = []
for i, (title, sub) in enumerate(STEPS):
    y_bottom = y - BOX_H
    bottoms.append(y_bottom)

    # 步骤框
    box = FancyBboxPatch(
        (BOX_X0, y_bottom), BOX_W, BOX_H,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.6, edgecolor=BOX_EDGE, facecolor=BOX_FACE, zorder=2,
    )
    ax.add_patch(box)

    # 编号徽章
    badge = Circle((BOX_X0 + 0.38, y_bottom + BOX_H / 2), 0.26,
                   facecolor=BADGE, edgecolor="none", zorder=3)
    ax.add_patch(badge)
    ax.text(BOX_X0 + 0.38, y_bottom + BOX_H / 2, str(i + 1),
            ha="center", va="center", fontsize=14, fontweight="bold", color="white", zorder=4)

    # 标题 + 说明
    tx = BOX_X0 + 0.82
    ax.text(tx, y_bottom + BOX_H - 0.42, title,
            ha="left", va="center", fontsize=16, fontweight="bold", color=INK, zorder=4)
    ax.text(tx, y_bottom + 0.34, sub,
            ha="left", va="center", fontsize=11, color=SUB, zorder=4)

    # 步骤间向下箭头（最后一步除外）
    if i < len(STEPS) - 1:
        ax.annotate(
            "", xy=(BOX_X0 + BOX_W / 2, y_bottom - GAP + 0.06),
            xytext=(BOX_X0 + BOX_W / 2, y_bottom - 0.02),
            arrowprops=dict(arrowstyle="-|>", color=BOX_EDGE, lw=2.0, mutation_scale=22),
            zorder=2,
        )

    y = y_bottom - GAP

# ---- 双 AI 标注（第 3/4/5 步右侧，箭头换行处） ----
step3_bottom = bottoms[2]
step4_top = bottoms[3] + BOX_H
step4_bottom = bottoms[3]
step5_top = bottoms[4] + BOX_H

right_x = BOX_X1 + 0.12
# 诊断 AI（第3→4 之间）
ax.text(BOX_X1 + 0.22, (step3_bottom + step4_top) / 2, "诊断 AI\n判断「现在什么状态」",
        ha="left", va="center", fontsize=10.5, color=ACCENT_DIAG, fontweight="bold")
ax.plot([BOX_X1 + 0.02, right_x + 0.28], [(step3_bottom + step4_top) / 2, (step3_bottom + step4_top) / 2],
        ls=(0, (3, 3)), lw=1.0, color=ACCENT_DIAG, zorder=1)
# 教练 AI（第4→5 之间）
ax.text(BOX_X1 + 0.22, (step4_bottom + step5_top) / 2, "教练 AI\n决定「该怎么帮」",
        ha="left", va="center", fontsize=10.5, color=ACCENT_COACH, fontweight="bold")
ax.plot([BOX_X1 + 0.02, right_x + 0.28], [(step4_bottom + step5_top) / 2, (step4_bottom + step5_top) / 2],
        ls=(0, (3, 3)), lw=1.0, color=ACCENT_COACH, zorder=1)
# 互校（连接两个标注的双向箭头）
mutual_x = BOX_X1 + 0.55
ax.annotate("", xy=(mutual_x, step5_top - 0.10), xytext=(mutual_x, step3_bottom + 0.18),
            arrowprops=dict(arrowstyle="<|-|>", color=ACCENT_COACH, lw=1.4, mutation_scale=16), zorder=1)
ax.text(mutual_x, (step4_bottom + step4_top) / 2, "互校",
        ha="center", va="center", fontsize=10.5, color=ACCENT_COACH, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor="none"))

# ---- 左侧回馈回路（第 6 步回到第 1 步） ----
loop = FancyArrowPatch(
    (LOOP_X, bottoms[-1] + 0.2), (LOOP_X, bottoms[0] + BOX_H - 0.2),
    arrowstyle="-|>", mutation_scale=22, color=LOOP, lw=2.0,
    connectionstyle="arc3,rad=-0.15", zorder=1,
)
ax.add_patch(loop)
ax.text(LOOP_X - 0.06, (bottoms[-1] + bottoms[0] + BOX_H) / 2,
        "持续观察 · 状态不断更新",
        rotation=90, ha="center", va="center", fontsize=11, color=LOOP, fontweight="bold")

plt.tight_layout(pad=0.4)
out = "docs/for-schools-flow.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
print("saved", out)