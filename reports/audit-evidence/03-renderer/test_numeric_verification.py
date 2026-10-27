"""Numerical-correctness evidence for the v2.3 audit (F-04 / F-09 / F-11).
Proves NUMBERS, not just crash-free rendering. Run with -I."""
import sys, os
WT = r"E:\claude\Wafer Map Oct\Wafer_tool_slim\Wafer_tool_slim"
sys.path.insert(0, WT)
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from wafer_tool.geometry import build_wafer_grid, far_from_data_mask
from wafer_tool.plotting import draw_wafer_ax
from wafer_tool.config import PlotConfig

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")

# CHK-0401 planar field z = 2x + 3y + 10, exact under linear interpolation inside hull
gx, gy = np.meshgrid(np.arange(0, 11.0), np.arange(0, 11.0))
x = gx.ravel().astype(np.float32); y = gy.ravel().astype(np.float32)
z = (2*x + 3*y + 10).astype(np.float32)
xi, yi, zi, *_ = build_wafer_grid(x, y, z, resolution=100, radius_factor=1.05, die_margin=0.5)
inside = (xi >= 1) & (xi <= 9) & (yi >= 1) & (yi <= 9) & ~np.isnan(zi)
err = np.abs(zi[inside] - (2*xi[inside] + 3*yi[inside] + 10))
check("CHK-0401 planar interp exact (inside hull)", err.max() < 0.05, f"max_abs_err={err.max():.2e}")

# CHK-0402 constant field z = 50
zc = np.full_like(z, 50.0)
_, _, zic, *_ = build_wafer_grid(x, y, zc, resolution=100, die_margin=0.5)
vc = zic[~np.isnan(zic)]
check("CHK-0402 constant field stays 50", np.allclose(vc, 50.0, atol=1e-3), f"range=[{vc.min():.4f},{vc.max():.4f}]")

# CHK-0406 far_from_data_mask distance semantics (max_dist = 4)
sx = np.array([0.0, 10, 0, 10]); sy = np.array([0.0, 0, 10, 10])
qx = np.array([[1.0, 5.0, 3.9/ (2**.5)*0+3.9]]); qy = np.array([[1.0, 5.0, 0.0]])
# point (1,1): nearest corner dist 1.414 (<4 -> near/False); (5,5): dist 7.07 (>4 -> far/True); (3.9,0): dist 3.9 (<4 -> False)
m = far_from_data_mask(np.array([[1.0,5.0,3.9]]), np.array([[1.0,5.0,0.0]]), sx, sy, 4.0)
check("CHK-0406 mask <4=near, >4=far", list(m.ravel()) == [False, True, False], f"mask={list(m.ravel())}")

# CHK-0403 degenerate (<4 points) does NOT fabricate a surface
fig, ax = plt.subplots()
sub3 = pd.DataFrame({"x":[1.,2,3],"y":[1.,2,3],"value":[10.,20,30]})
ok3 = draw_wafer_ax(ax, sub3, "w", PlotConfig(t_low=15, t_high=25))
ax.clear()
sub4 = pd.DataFrame({"x":[1.,5,1,5],"y":[1.,1,5,5],"value":[10.,20,30,40]})
ok4 = draw_wafer_ax(ax, sub4, "w", PlotConfig(t_low=15, t_high=25))
check("CHK-0403 <4 pts rejected, >=4 pts drawn", (ok3 is False) and (ok4 is True), f"3pts={ok3} 4pts={ok4}")

# CHK-0408 / INV-03 raw-value invariance across extrapolate + colour-reverse
sub = pd.DataFrame({"x":np.tile(np.arange(5),5).astype(float),
                    "y":np.repeat(np.arange(5),5).astype(float),
                    "value":np.linspace(0,100,25)})
orig = sub["value"].to_numpy(copy=True)
for ex in (False, True):
    for hg in (False, True):
        ax.clear()
        draw_wafer_ax(ax, sub, "w", PlotConfig(t_low=30, t_high=70, extrapolate=ex,
                                               high_is_green=hg, show_missing_grey=True))
check("CHK-0408 raw values unmutated by rendering", np.array_equal(sub["value"].to_numpy(), orig),
      "df.value identical after 4 renders")

# CHK-0413 log-scale edge cases: all-zero and negative data do not crash
try:
    ax.clear(); zall0 = sub.copy(); zall0["value"] = 0.0
    r0 = draw_wafer_ax(ax, zall0, "w", PlotConfig(t_low=1, t_high=10, use_log=True))
    ax.clear(); zneg = sub.copy(); zneg["value"] = -sub["value"] - 1
    rn = draw_wafer_ax(ax, zneg, "w", PlotConfig(t_low=1, t_high=10, use_log=True))
    check("CHK-0413 log of all-zero/negative no crash", True, f"allzero={r0} neg={rn}")
except Exception as exc:
    check("CHK-0413 log of all-zero/negative no crash", False, repr(exc))
plt.close(fig)

# INV-03 (stats): colour reversal does not change classification counts
from wafer_tool.statistics import calculate_8_condition_statistics
df = pd.DataFrame({"lot":["L"]*25,"wafer":["01"]*25,
                   "x":sub["x"],"y":sub["y"],"value":np.linspace(0,100,25)})
a = calculate_8_condition_statistics(df, PlotConfig(t_low=30,t_high=70,high_is_green=False))
b = calculate_8_condition_statistics(df, PlotConfig(t_low=30,t_high=70,high_is_green=True))
check("INV-03 stats invariant under colour reverse", repr(a)==repr(b) or str(a)==str(b),
      "8-condition result identical when only high_is_green flips")

n_pass = sum(1 for _,ok,_ in results if ok)
print(f"\n=== NUMERICAL VERIFICATION: {n_pass}/{len(results)} PASS ===")
sys.exit(0 if n_pass==len(results) else 1)
