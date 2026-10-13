import os
import subprocess
import sys

def main():
    env = os.environ.copy()
    env["NODE_PATH"] = "C:/Users/26730/AppData/Local/hermes/skills/anti-bot-scraper/node_modules"
    js_path = "C:/Users/26730/educational_benchmark/scripts/login_sso.js"

    print(">>> 正在启动可视化浏览器登录窗口，请准备手机微信扫码或输入验证码...")
    sys.stdout.flush()

    proc = subprocess.Popen(
        ["node", js_path],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    for line in iter(proc.stdout.readline, ""):
        print(line, end="")
        sys.stdout.flush()

    proc.wait()
    if proc.returncode == 0:
        print("\n>>> 🎉 登录流程顺利完成！最新 VIP Cookie 已就绪。")
    else:
        print(f"\n>>> 登录未完成或已取消 (Exit code: {proc.returncode})。")
        sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
