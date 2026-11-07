# 11.8 展台 Runbook（sidekick booth）

分支 `showcase-1108`，运行 stage 3（完整展台）。详细说明见 `docs/SHOWDAY_1108.md`。

---

## 0. 今晚出发前

- [ ] 推送：`git push -u origin showcase-1108`
- [ ] 打印牌子：`docs/booth_sign/booth_sign.pdf`（A4 横版）
- [ ] 电脑、CoreS3 充电；舵机电源 / 适配器
- [ ] 确认 `.env` 里有 `GEMINI_API_KEY`（展台用 gemini-3.8-flash）
- [ ] 带上：机器人、头部摄像头（InnoMaker）、舵机 USB 板、CoreS3 线、电源、USB hub、延长线、牌子、几样好识别的道具（水瓶、杯子、香蕉、小玩偶）
- [ ] 备一个手机热点（场地 Wi-Fi 不稳时用）

## 1. 到场布置（约 15 分钟）

- 机器人前面留 **1–1.5 m 空地**：观众从这里走近，它才会醒并跟着人。
- 摄像头前面不要挡；背后不要正对强光或窗户（逆光时认不出人脸）。
- 牌子放在机器人正前方的桌上。
- 电脑放在机器人侧后方，屏幕朝向你自己，打开 live 窗口。
- **CoreS3 开机时不要碰它的头**：触摸传感器开机时会自动校准，这时碰着它，之后摸头就不灵。

## 2. 开机顺序

```bash
cd ~/Documents/potatobot/showcase
conda activate sidekick
git pull                       # 如果在另一台电脑上改过
```

| 步骤 | 命令 | 正常结果 |
|---|---|---|
| ① 舵机 | `python3 robot/tools/check_bus.py` | 三个舵机都有响应，电压 **5–6 V** |
| ② CoreS3 | `python3 robot/tools/tof_test.py` | 显示 **v21**，手靠近数字会变；Ctrl-C 退出 |
| ③ 摄像头编号 | `python3 noticebot_loop.py --list-cams` | 记下 InnoMaker 的编号 N |
| ④ 网络（可选） | `python3 robot/tools/net_check.py` | 能连上 Gemini，单次几秒内返回 |
| ⑤ **开始** | `python3 sidekick_loop.py --stage 3 --cam N --cores3 --view` | 机器人低头睡着，脸 `-_- zz` |

停止：在终端按 **Ctrl-C**，它会躺下并放松舵机。

- **换下一位观众**：在 live 窗口按 **n**（或在终端输入 `n` 回车）。它回到刚启动的状态（低头睡着），但**上一位给它看的东西还记着**。下一位走近时，它会先点头说 "Someone showed me … I'm still looking out for it!"
- 记住的东西存在 `session_feed/booth_memory.json`，**重启程序也不会丢**。想清空（比如开展前），启动时加 `--forget`。

## 3. 开场自测（5 分钟，按牌子走一遍）

| 做什么 | 应该看到 | 终端 |
|---|---|---|
| 摸头 | 醒来，往手里蹭 | `[brain] phase LOOK` |
| 走到 ~1.5 m 内 | 抬头看你、跟着你 | `[sense] NEAR (size 30%…)` |
| 站在 1–2 m 处挥手（手举到头旁边左右摆） | 屏幕上的脸挥手 `\^o^`/`^o^/`，头弹两下，"嘀嘀"两声，显示 "Hi!" | `[brain] wave waving back` |
| 再走到 ~0.75 m 内 | 一下一下往前探，灯变亮，`*o_o*` | `[brain] close very close (57%)` |
| 把水瓶**举到它眼前**（~30 cm），停 1 秒 | 后缩，"hm?"，前探，然后点头 + 同意音效；屏幕显示 "OK! I'll look out for …" | `[identify] '…' -> watching for '…'` |
| 收起来 **3 秒以上**，再拿出来 | 指向它，叫唤 | `[brain] found …` |
| 叫唤时摸头 | 点头，回来看你 | `[brain] phase LOOK` |
| 走开 | ~6 s 后抬头打盹；有目标时不会低头睡 | `[brain] phase DOZE` |

全部正常就开始。如果有一步不对，看下面的故障速查。

## 4. 运行中

- 一组观众玩完、下一组过来时按 **n**，让它重新开始并把上一个东西"转告"给新观众。

- 尽量不要干预，让观众自己看牌子玩。只在有人卡住时说一句"举起来给它看"或者"摸摸它的头"。
- 旁边有人工作嫌吵：重启时加 `--mute`。
- 每次运行的日志自动保存在 `session_feed/sidekick_<时间>/run.log`。记下出问题时的大概时间。
- 舵机连续运行很久后摸一下是否发烫；烫的话 Ctrl-C 休息 10 分钟。

## 5. 故障速查

| 现象 | 先做这个 |
|---|---|
| 不醒 | 看终端 `[sense]`：显示 nobody 就是没认出人（检查光线、摄像头编号）。睡着时只有摸头或手靠近传感器才能叫醒它 |
| 不好奇 | 东西要**举到它眼前、在画面中间、停 1 秒**；live 窗口里东西旁边的百分比要 ≥ 4.5%（`SHOW_AREA`）。小东西要拿得更近 |
| 显示 "I couldn't tell what that was" | 网络问题：跑一下 `net_check`；不行就重启并加 `--offline`（用检测器自己的词，不调用 Gemini） |
| 东西拿回来它不叫 | 要先**完全藏起来 3 秒**；看 `[identify] … watching for '…'`，词太偏的东西（检测器认不出）换一样常见的道具 |
| 打招呼也被当成在给它看 | 看那件东西的百分比，把 `SHOW_AREA` 调高一点 |
| 挥手没反应 | live 窗口右上角有没有 "hand up"：没有 = 手没举过肩或身体没被认出（站远一点，让肩膀进画面）；有但不回应 = 挥的幅度再大一点 |
| "很近"太早或太晚触发 | 记下终端里显示的百分比，之后调 `CLOSE_ENTER_FRAC`（`session/sidekick_brain.py`） |
| 头不动、卡住 | Ctrl-C，跑 `check_bus.py`，看电压，再重新开始 |
| 舵机抖、电压 < 5 V | 换电源或给电池充电 |
| CoreS3 脸不显示 / 没声音 | 重新插 CoreS3，跑 `tof_test.py` 确认 v21 |
| 摸头没反应 | 重新插 CoreS3，**插的时候别碰头** |
| 摄像头画面不对 / 黑屏 | 插拔后编号可能变了：再跑 `--list-cams` |
| 启动时出现 `did not arrive: nod=…` | 偶尔出现可以忽略；每次都出现就检查点头关节是不是卡住 |
| 一开机就说 "Someone showed me …"（昨天的东西） | 开展前忘了清：Ctrl-C，加 `--forget` 重新启动 |
| 实在不行 | 换成论文 demo：Ctrl-C，按 `docs/SHOWDAY.md` 运行 |

## 6. 收尾

- [ ] Ctrl-C，等它躺下放松后再断电
- [ ] 把有问题的那几次运行的 `session_feed/sidekick_<时间>/` 文件夹名记下来（发给我看 run.log）
- [ ] 看完日志后**删除 `session_feed/` 里当天的照片**：找到东西时的截图里可能拍到了观众
- [ ] 收线，把舵机和摄像头包好
