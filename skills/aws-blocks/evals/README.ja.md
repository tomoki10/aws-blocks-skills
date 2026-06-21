---
lang: ja
source: README.md
source_sha: 143413b7b4f231f57044a80a24e6727120d26166
---

> 📖 これは [README.md](README.md) の日本語訳です。**正典は英語版**で、差異がある場合は英語が優先されます。

# AWS Blocks スキル — 挙動 Eval

このディレクトリは `aws-blocks` スキルの**挙動 eval**と、A/B ベンチマーク（スキルあり vs. スキルなし）
を実行するためのフィクスチャ・ドキュメントを格納しています。

## 目的

A/B ベンチマークが答える問いは一つ：**スキルは本当に役に立っているか？**

各 eval プロンプトを使い捨てサンドボックスに対して 2 回実行します。1 回は `skills/aws-blocks/` へのアクセスあり（with_skill）、
もう 1 回はスキルコンテキスト無し（without_skill）。複数回の実行にわたって pass 率・レイテンシー・トークン使用量を比較します。

## ディレクトリ構成

```
evals/
  evals.json              — eval 定義: プロンプト・フィクスチャ・アサーション
  fixtures/
    blank-ifc/index.ts    — データ Block なしの最小 IFC（eval 0, 1 用）
    todos-seeded/index.ts — todos DistributedTable が既に定義済みの IFC（eval 2 用）
  README.md               — 英語版（正典）
  README.ja.md            — このファイル
```

ベンチマーク出力（skill-creator ツールが生成、コミットしない）:

```
<workspace>/iteration-N/
  eval-0/
    with_skill/run-1/{transcript.md, outputs/, grading.json, timing.json}
    without_skill/run-1/{...}
  eval-1/ ...
  eval-2/ ...
  benchmark.json
  benchmark.md
```

## フィクスチャ

各 eval は `evals.json` の `fixture` フィールドでフィクスチャを指定します。各 run の前に executor が
`my-app` を一時サンドボックスにコピーし、`aws-blocks/index.ts` を指定フィクスチャで上書きします。
これにより、本番プロジェクトが変化しても再現可能な初期状態が保証されます。

| フィクスチャ | IFC 状態 | 使用する eval |
|---|---|---|
| `blank-ifc` | Scope + AuthBasic + 空の ApiNamespace（データ Block なし） | eval 0, 1 |
| `todos-seeded` | todos DistributedTable が既に定義済み | eval 2 |

## アサーション（採点基準）

各 eval は `expectations` 配列を持ちます。これは executor の transcript と outputs に対して grader が
チェックする自然言語アサーションのリストです。grader はアサーションごとの pass/fail と総合スコアを
`grading.json` に出力します。

現在のアサーション内容は `evals.json` を参照してください。

## ベンチマークの実行

`/run-evals` コマンドを使います。サンドボックス複製 → 実行 → 採点 → 集計の全フローを自動化します。
詳細は `.claude/commands/run-evals.md` のランブックを参照してください。

ベンチマークツールは skill-creator プラグインにあります:

```
~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/
```

スモークテスト（eval 2 のみ、各 config 1 回）:

```sh
# リポジトリルートから
claude /run-evals --eval 2 --runs 1
```

フルベンチマーク（3 eval × 2 config × 3 run）:

```sh
claude /run-evals --runs 3
```
