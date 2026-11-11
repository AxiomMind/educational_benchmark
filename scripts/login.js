// 交互登录：本地保存会话，不输出 Cookie 或 Token。
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline/promises');

async function main() {
  const cookiePath = path.resolve(__dirname, '../data/xkw_cookies.json');
  const browser = await chromium.launch({ headless: false });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('https://zujuan.xkw.com/gzls/', { waitUntil: 'domcontentloaded' });
    console.log('请在浏览器中完成登录，并回到组卷网页面。');
    const terminal = readline.createInterface({ input: process.stdin, output: process.stdout });
    try {
      await terminal.question('确认页面已登录后，按回车保存本地会话：');
    } finally {
      terminal.close();
    }
    const cookies = (await context.cookies()).filter(cookie => {
      const domain = cookie.domain.replace(/^\./, '');
      return domain === 'xkw.com' || domain.endsWith('.xkw.com');
    });
    if (!cookies.some(cookie => cookie.name === 'user_token' && cookie.domain.includes('zujuan'))) {
      throw new Error('尚未获取组卷网会话，请确认登录完成后重试。');
    }
    fs.mkdirSync(path.dirname(cookiePath), { recursive: true });
    fs.writeFileSync(cookiePath, JSON.stringify(cookies, null, 2), { mode: 0o600 });
    console.log('已保存 data/xkw_cookies.json（Git 忽略）。');
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
