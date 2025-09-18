#!/bin/bash
# 目标：通过 SSH 在 Debian 系统上初始化环境并启动 sing-box-v2ray
# 注意：避免在脚本中明文存放私密凭据，建议使用 deploy 时传入或使用 SSH key。

set -euo pipefail
LOG_PREFIX="[init_env]"

err_exit() {
	echo "$LOG_PREFIX ERROR: $1" >&2
	exit ${2-1}
}

info() { echo "$LOG_PREFIX INFO: $*"; }

# 1) 安装 git（Debian/Ubuntu）如果缺失
if ! command -v git >/dev/null 2>&1; then
	info "git not found, attempting to install (apt-get)"
	if command -v apt-get >/dev/null 2>&1; then
		sudo apt-get update -y || err_exit "apt-get update failed"
		sudo apt-get install -y git || err_exit "apt-get install git failed"
	else
		err_exit "apt-get not available; cannot install git on this system"
	fi
else
	info "git already installed"
fi

# 2) 克隆仓库（请改为使用 SSH URL 或在部署端注入凭据）
REPO_SSH_URL="https://gansxx:8j8U_0Jz92LsthdG17GxYW86MQp1OjQ1NXEK.01.100h7pp8l@jihulab.com/gansxx/sing-box-v2ray.git"
TARGET_DIR="/root/sing-box-v2ray"

if [ -d "$TARGET_DIR" ]; then
	info "Target dir $TARGET_DIR already exists - attempting to update"
	cd "$TARGET_DIR"
	git pull || err_exit "git pull failed in existing repo"
else
    # 主分支下载
	# info "Cloning repository $REPO_SSH_URL -> $TARGET_DIR"
	# git clone "$REPO_SSH_URL" "$TARGET_DIR" || err_exit "git clone failed"
	#测试分支下载
	echo "下载测试分支"
	info "Cloning repository $REPO_SSH_URL (test/test_alarm branch) -> $TARGET_DIR"
	git clone -b test/test_alarm --single-branch https://gansxx:8j8U_0Jz92LsthdG17GxYW86MQp1OjQ1NXEK.01.100h7pp8l@jihulab.com/gansxx/sing-box-v2ray.git
fi

# 3) 确认目录和脚本存在并可执行
if [ ! -d "$TARGET_DIR" ]; then
	err_exit "Expected directory $TARGET_DIR not found after clone"
fi

cd "$TARGET_DIR"
 
# Helper: ensure a file exists in $TARGET_DIR and is executable
make_all_files_executable() {
	info "Making all regular files under $TARGET_DIR executable (recursive)"
	# find regular files and set the executable bit; use -print0/xargs -0 to handle spaces
	if ! find "$TARGET_DIR" -type f -print0 | xargs -0 -r chmod +x; then
		err_exit "failed to chmod +x files under $TARGET_DIR"
	fi
}
# 对整个目标目录递归授权（替代逐个文件授权）
make_all_files_executable

# 4) 执行脚本（按需可以把这些放在后台或使用 systemd）
info "Running sb.sh"
./sb.sh || err_exit "sb.sh failed"

info "Running sb_move.sh"
./sb_move.sh || err_exit "sb_move.sh failed"

info "Environment initialized Successfully."