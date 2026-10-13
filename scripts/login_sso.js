const { chromium } = require('playwright');
const fs = require('fs');

const COOKIE_PATH = 'C:/Users/26730/educational_benchmark/data/xkw_cookies.json';
const LOGIN_URL = 'https://sso.xkw.com/login?appId=10001&returnUrl=https%3A%2F%2Fzujuan.xkw.com%2Fgzls%2F';

(async () => {
  console.log('>>> 正在启动可视化浏览器，直接打开学科网官方扫码登录页面...');
  const browser = await chromium.launch({
    headless: false,
    args: [
      '--start-maximized',
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox'
    ]
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 850 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  });

  const page = await context.newPage();
  console.log('>>> 正在加载登录页面...');

  try {
    await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (err) {
    console.log('登录页加载提示:', err.message);
  }

  console.log('\n================================================================');
  console.log(' 登录页面已就绪！页面中央已显示微信扫码登录二维码。');
  console.log(' 请使用刚刚充值了会员的微信账号扫码（或点击右侧密码/验证码登录）。');
  console.log(' 扫码成功后，页面会自动跳转回组卷网，脚本将自动保存 VIP Cookie！');
  console.log('================================================================\n');

  const startTime = Date.now();
  let loggedIn = false;

  // 10 分钟充足等待时间
  while (Date.now() - startTime < 600000) {
    try {
      if (page.isClosed()) {
        console.log('>>> 浏览器窗口已被手动关闭。');
        break;
      }

      await page.waitForTimeout(2000);

      const currentUrl = page.url();
      const cookies = await context.cookies();
      const cookieNames = cookies.map(c => c.name.toLowerCase());

      const hasAuthCookie = cookieNames.includes('user_token') || cookieNames.includes('userid') || cookieNames.includes('tgc');

      // 只要 URL 重定向到了 zujuan.xkw.com，或者已经具有核心登录令牌，且不在登录页上
      if ((hasAuthCookie && !currentUrl.includes('/login')) || (currentUrl.includes('zujuan.xkw.com') && hasAuthCookie)) {
        console.log('>>> 🎉 捕获到扫码登录成功！当前页面:', currentUrl);
        console.log('>>> 正在同步并刷新 VIP 完整会话 Cookie...');

        // 稍微等待 4 秒，确保组卷网全站 Cookie 写入完毕
        await page.waitForTimeout(4000);

        const allCookies = await context.cookies();
        fs.writeFileSync(COOKIE_PATH, JSON.stringify(allCookies, null, 2), 'utf8');
        console.log('>>> 🎉 最新 VIP Cookie 已成功保存到:', COOKIE_PATH);
        loggedIn = true;
        break;
      }
    } catch (err) {
      if (err.message && err.message.includes('closed')) {
        console.log('>>> 浏览器窗口已关闭。');
        break;
      }
    }
  }

  if (!loggedIn) {
    console.log('>>> 登录未完成或等待超时。');
  }

  try {
    await page.waitForTimeout(2000);
    await browser.close();
  } catch (e) {}

  process.exit(loggedIn ? 0 : 1);
})();
