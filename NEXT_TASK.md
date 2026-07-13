# NEXT_TASK.md

## Next Task

Screen every eligible new train state from Website Dataset Extension v2 for
robust information-set teacher candidates, then append accepted labels to the
frozen teacher v2 base.

Do not run website games or train a model in this task, even if the teacher
training gate reaches 20 independent games.

## Locked Conclusion From the Previous Stage

- Extension v2 contains 70 bot-only games, 40 wins, 30 losses, 1,753 decisions,
  and 49,549 legal candidates; rejected files or games: 0.
- The physical train/development partition contains 882 consistent decisions:
  718 train and 164 development.
- All 12 Supplement v2 games and all 280 of their decisions entered train.
- Extension v1 games, splits, sessions, source hashes, and the nine-game locked
  set are unchanged.
- Extension v2 manifest content hash:
  `31c5bc501286ac41d3a791811c7089200e49097132bfd886aa10d281c5ddb27e`.
- The current teacher v2 base remains frozen at 11 labels from 11 independent
  games; the 20-game training gate is closed.

## Authoritative Inputs

- Load only `website_danzero_shadow_extension_v2.train_dev.pth` for state
  selection and rollout evaluation.
- Train/development partition SHA-256:
  `03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60`.
- Restrict candidate states to these new train game IDs:
  `13985`, `13986`, `13987`, `13989`, `13991`, `13992`, `13994`, `13996`,
  `13997`, `13999`, `14000`, and `14002`.
- Use `website_information_set_teacher_dataset_v2.pth` only as the frozen base
  teacher dataset when rebuilding accepted labels.
- Frozen teacher v2 SHA-256:
  `620b378675ef1964f16043c7c2cdd4d75dc8db3bb7377cab773c3bbe8aec250f`.
- Write a new `website_information_set_teacher_dataset_v3.pth`; do not
  overwrite teacher v2.
- Do not load `website_danzero_shadow_extension_v2.pth` or
  `website_danzero_shadow_extension_v2.locked_test.pth`.

## Constraints

- Do not access or use locked test for screening, candidate design, threshold
  tuning, checkpoint selection, or any conclusion.
- Use only decision-time information and the `website_oracle` legal mask.
- Hidden-card simulation must use legal information-set determinization.
- Do not use opponent hands, teammate hands, future actions, future states, or
  post-game-only information as features or labels.
- Do not modify `tempo_baseline`, the website protocol, leaderboard Elo
  semantics, teacher thresholds, or frozen artifacts.
- Greedy-only results are screening signals and must never become strong
  labels directly.
- Strong labels must have at least 16 complete paired rollouts, acceptable
  candidate-return variance, positive advantage and 95% lower bound, and
  positive advantages against both greedy and frozen-tempo continuations.
- Do not weaken thresholds or repeatedly expand low-evidence candidates to
  force the 20-game gate.
- Do not continue into training, offline evaluation, or website play after the
  teacher dataset conclusion is locked.

## Required Work

1. Verify Git state and re-read the canonical handoff files.
2. Verify the train/development partition hash, partition role, information-set
   consistency, and zero locked-test samples before screening.
3. Enumerate all 280 new train decisions. Report eligible and ineligible counts
   and reasons; screen every state eligible under the existing public-hand-count
   and information-set rules.
4. Run the existing stable-seed greedy-only screening over every eligible new
   state and record complete candidate/rollout coverage. Do not emit labels from
   this pass.
5. Select only high-evidence signals for 16-rollout greedy-plus-frozen-tempo
   confirmation, using common deterministic hidden-card assignments across
   continuation profiles.
6. Record rollout count, hidden-card sampling method, mean return, candidate and
   paired variance, candidate advantage, 95% lower bound, confidence,
   completion rate, and per-profile advantages for every confirmed case.
7. Accept only labels that pass the existing completeness, variance, advantage,
   confidence, and dual-continuation robustness gates.
8. Rebuild teacher v3 from the frozen teacher v2 base plus accepted new labels.
   Verify all 11 old labels are unchanged, every new source is train, and every
   physical action remaps to the original legal 54-dimensional action.
9. Report the resulting independent high-confidence teacher-game count and
   whether the 20-game gate is reached. Do not train in this stage.
10. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md`; update the
    durable progress document, run the narrowest relevant validation, then
    commit and push.

## Success Criteria

- New train decisions enumerated: 280; every eligible state is screened.
- Locked-test samples loaded or used: 0.
- Hidden/future information leaks: 0.
- Greedy-only labels accepted: 0.
- Incomplete rollout files accepted: 0.
- Every accepted new label has at least 16 complete paired rollouts, acceptable
  candidate variance, positive mean advantage and 95% lower bound, and positive
  greedy and frozen-tempo continuation advantages.
- Frozen teacher v2 labels changed or removed: 0.
- Teacher label physical-action remap errors: 0.
- Teacher v3 reports accepted new labels, total labels, independent games, and
  the 20-game gate accurately.
- Website games, model training, offline evaluation, and model-controlled
  website play performed in this stage: 0.
- Runtime credential occurrences in new tracked/curated files: 0.
- The next single-stage Goal prompt is written only after the teacher v3
  conclusion is locked.

## Stage Goal Prompt

```text
请创建一个阶段 Goal：
目标名称：完成 extension v2 新增 12 个 train 游戏的信息集 teacher candidate 全量筛选、稳健确认和 teacher v3 重建。
约束：本阶段不运行网站对局、不训练模型、不进行离线能力评估，不修改 tempo_baseline、网站协议、leaderboard Elo 语义、teacher 阈值或冻结 artifacts。只能加载 website_danzero_shadow_extension_v2.train_dev.pth，其 SHA-256 必须为 03d1a0967429fd75433ea3753a96c4bce43660f636a7cf9801140bd02777cc60；不得加载 complete bundle 或 locked_test partition。只筛选 game_id 13985、13986、13987、13989、13991、13992、13994、13996、13997、13999、14000、14002。只能使用决策点可见信息和 website_oracle legal mask；隐藏牌模拟必须采用合法信息集 determinization。greedy-only 结果只能用于初筛，不能直接成为强标签。强标签必须至少有 16 个完整配对 rollout，candidate variance 合格，优势和 95% 下界为正，并且 greedy 与 frozen-tempo continuation 优势都为正。即使独立 teacher 游戏达到 20，本阶段也不得训练。
任务：1. 检查 Git 与交接文件。2. 核验 train_dev hash、partition role、全样本信息集一致和 locked_test 为 0。3. 枚举 280 个新增 train 决策，报告现有规则下的 eligible/ineligible 数量和原因，并筛选每个 eligible 状态。4. 使用稳定种子完成全量 greedy-only 初筛，记录完整候选与 rollout 覆盖，不接受标签。5. 只对高证据信号运行 16-rollout greedy+frozen-tempo 确认，两种 continuation 共用确定性隐藏牌分配。6. 记录 rollout count、隐藏牌采样、均值、candidate/paired variance、优势、95% 下界、置信度、完成率和 profile 优势。7. 只接受通过现有完整性、方差、优势、置信度和双 continuation 稳健门的标签。8. 以 website_information_set_teacher_dataset_v2.pth 为冻结基线重建 website_information_set_teacher_dataset_v3.pth，核验 11 条旧标签不变、新 source 全为 train、physical action 合法映射到原始 54 维动作。9. 报告 teacher 总标签、独立游戏和 20-game gate，但不训练。10. 更新交接和进展文档，运行最窄相关验证，commit 并 push。
验收：280 个新增 train 决策全部枚举且所有 eligible 状态完成筛选；locked_test 访问 0；隐藏或未来信息泄漏 0；greedy-only 接受标签 0；不完整 rollout 接受 0；每个新增标签至少 16 个完整配对 rollout，并通过 candidate variance、正优势、正 95% 下界以及 greedy/frozen-tempo 双正门槛；teacher v2 旧标签改动或删除 0；physical-action remap error 0；teacher v3 准确报告新增、总标签、独立游戏和 20-game gate；本阶段网站对局、模型训练、离线评估、模型控制网站均为 0；新 tracked/curated 文件凭据出现 0；只有全部验收、交接、验证、commit 和 push 成功后才能完成 Goal。
```
