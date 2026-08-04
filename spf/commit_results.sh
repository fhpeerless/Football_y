#!/bin/bash
# spf/commit_results.sh - 提交并推送指定的结果文件（供 spf_ai.yml 调用）
# 用法: bash spf/commit_results.sh "提交信息" "文件glob1" "文件glob2"...
# 需要环境变量: PUSH_URL（含 token 的远程地址）、GITHUB_REF_NAME（GitHub Actions 自动提供）
set -e

COMMIT_MSG="$1"
shift || true

git config --global user.name "GitHub Actions"
git config --global user.email "github-actions[bot]@users.noreply.github.com"

# 只 add 显式传入的文件路径（支持 glob）
git add "$@" 2>/dev/null || true

if git diff --cached --quiet; then
  echo "没有更改可提交，跳过push步骤"
  exit 0
fi

git commit -m "$COMMIT_MSG"

# 远端 main 可能被本地 sync_to_github.py 强推改写、或与其他工作流并发，
# 直接 push 会因历史分叉被拒；失败时先 fetch + rebase 远端再重试
for attempt in 1 2 3; do
  echo "第 ${attempt} 次尝试 push..."
  if git push "$PUSH_URL" "HEAD:$GITHUB_REF_NAME"; then
    echo "push 成功"
    exit 0
  fi
  echo "push 失败，拉取远端最新代码并变基后重试..."
  git fetch "$PUSH_URL" "$GITHUB_REF_NAME" || exit 1
  if ! git rebase FETCH_HEAD; then
    echo "与远端代码冲突，自动变基失败（远端未受影响，可稍后运行本地 sync_to_github.py 合并同步）"
    git rebase --abort
    exit 1
  fi
done
echo "push 连续 3 次失败，工作流退出"
exit 1
