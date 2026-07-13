# NEXT_TASK.md

## Next Task

Screen only the newly collected extension v1 train/development states for
robust information-set teacher candidates, then rebuild the teacher dataset if
strong labels are found.

Do not run website games. Do not train a model in this task.

## Authoritative Inputs

- Use only `website_danzero_shadow_extension_v1.train_dev.pth` for state
  selection and rollout evaluation.
- Restrict candidate states to new game IDs 13956-13963.
- Use `website_information_set_teacher_dataset_v1.pth` only as the frozen base
  teacher dataset when rebuilding accepted labels.
- Do not load `website_danzero_shadow_extension_v1.pth` or
  `website_danzero_shadow_extension_v1.locked_test.pth`; both contain or expose
  locked-test samples.

## Constraints

- Do not access or use `locked_test` for screening, candidate design,
  threshold tuning, or checkpoint selection.
- Use only decision-time information and the `website_oracle` legal mask.
- Hidden-card simulation must use legal information-set determinization.
- Do not use opponent hands, teammate hands, future actions, future states, or
  post-game-only information as features or labels.
- Do not modify `tempo_baseline`, the website protocol, or leaderboard Elo
  semantics.
- Strong labels must be complete, low-variance, confidence-positive, and
  positive against both greedy and frozen-tempo continuations.
- Do not weaken teacher thresholds to force acceptance.

## Required Work

1. Verify the Git state and re-read the handoff files.
2. Verify the train/development partition hash and reject any locked-test
   sample before screening.
3. Screen the new games for high-risk, high-value, or under-covered candidate
   states without using hidden or future information.
4. Run legal information-set rollout/search with deterministic recorded seeds.
5. For every evaluated candidate, record rollout count, hidden-card sampling
   method, mean return, return variance, paired candidate advantage, 95%
   confidence bound, completion rate, and continuation-profile advantages.
6. Accept only labels that pass the existing completeness, variance,
   advantage, confidence, and greedy-plus-frozen-tempo robustness gates.
7. Rebuild the teacher dataset from the frozen v1 base plus accepted new labels
   and verify physical-action remapping.
8. Report independent high-confidence teacher games and keep the training gate
   closed if the count is below 20.
9. Update `PROJECT_STATE.md`, `EXPERIMENTS.md`, and `NEXT_TASK.md`, run the
   narrowest relevant tests, then commit and push.

## Success Criteria

- Locked-test samples loaded or used: 0.
- Hidden/future information leaks: 0.
- Incomplete rollout files accepted: 0.
- Teacher label remap errors: 0.
- Every accepted label has positive mean advantage, positive 95% lower bound,
  acceptable candidate-return variance, and positive greedy and frozen-tempo
  continuation advantages.
- No model training occurs unless at least 20 independent high-confidence
  teacher games exist and the coverage gate passes.
- The next single-stage Goal prompt is written after the conclusion is locked.

## Stage Goal Prompt

```text
请创建一个阶段 Goal：

目标名称：完成 extension v1 新增 train/development 状态的信息集 teacher candidate 筛选与 teacher dataset 重建。

约束：不进行网站对局，不让模型接管网站，不训练模型，不修改 tempo_baseline、服务器通信协议或 leaderboard Elo 语义。只能读取 website_danzero_shadow_extension_v1.train_dev.pth，并只筛选新增 game_id 13956-13963；不得加载 complete bundle 或 locked_test partition。只能使用真实决策点可见信息和 website_oracle legal mask；隐藏牌模拟必须采用合法的信息集 determinization。

任务：1. 检查 Git 与交接文件。2. 验证 train/development partition 且拒绝任何 locked_test 样本。3. 从新增状态中筛选高风险、高价值或覆盖不足的候选。4. 运行信息集 rollout/search，记录 rollout_count、hidden_card_sampling_method、mean_return、return_variance、candidate_advantage、95% confidence bound、completion_rate 和 continuation-policy advantages。5. 只接受完整、低方差、优势与置信界显著为正，且 greedy 和 frozen-tempo continuation 均为正的标签。6. 以 website_information_set_teacher_dataset_v1.pth 为 frozen base 重建 teacher dataset，并验证 physical-action remap。7. 检查 independent high-confidence teacher games 是否达到 20；不足 20 时不得训练。8. 更新交接文件、验证、commit 并 push。

验收：locked_test 访问为 0，隐藏/未来信息泄漏为 0，不完整 rollout 接受数为 0，teacher label remap error=0；所有接受标签均通过现有 completeness、variance、advantage、confidence 与 continuation robustness 门槛；未达到 20 个独立高置信 teacher games 时训练门保持关闭；输出下一阶段单一 Goal 提示词。
```
