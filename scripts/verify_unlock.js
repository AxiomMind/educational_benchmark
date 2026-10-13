const { chromium } = require('playwright');
const fs = require('fs');

const COOKIE_PATH = 'C:/Users/26730/educational_benchmark/data/xkw_cookies.json';
const VERIFY_URL = 'https://zujuan.xkw.com/17q29551974.html';

(async () => {
  console.log('>>> 正在打开安全验证窗口，请准备接收手机短信验证码...');
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

  const cookies = JSON.parse(fs.readFileSync(COOKIE_PATH, 'utf8'));
  await context.addCookies(cookies);

  const page = await context.newPage();
  console.log('>>> 正在加载安全验证页面...');

  try {
    await page.goto(VERIFY_URL, { waitUntil: 'commit', timeout: 30000 });
  } catch (err) {
    console.log('加载提示:', err.message);
  }

  console.log('\n================================================================');
  console.log(' 安全验证窗口已打开！');
  console.log(' 请在窗口中输入手机短信验证码，完成安全核验。');
  console.log(' 验证通过后，页面会自动刷新恢复试题页面，脚本将自动保存凭证并关闭。');
  console.log('================================================================\n');

  const startTime = Date.now();
  let unlocked = false;

  // 10 分钟等待时间
  while (Date.now() - startTime < 600000) {
    try {
      if (page.isClosed()) {
        console.log('>>> 浏览器窗口已被手动关闭。');
        break;
      }

      await page.waitForTimeout(2000);

      const title = await page.title();
      // 验证成功后，页面会自动 reload，标题不再是“安全验证”，而是试题名称或组卷网正常标题
      if (title && !title.includes('安全验证')) {
        console.log('>>> 🎉 恭喜！安全验证已通过！当前页面:', title.slice(0, 40));
        await page.waitForTimeout(3000);
        const freshCookies = await context.cookies();
        fs.writeFileSync(COOKIE_PATH, JSON.stringify(freshCookies, null, 2), 'utf8');
        console.log('>>> 🎉 最新解除风控的 Cookie 已成功保存到:', COOKIE_PATH);
        unlocked = true;
        break;
      }
    } catch (err) {
      if (err.message && err.message.includes('closed')) {
        break;
      }
    }
  }

  if (!unlocked) {
    console.log('>>> 验证未完成或等待超时。');
  }

  try {
    await page.waitForTimeout(2000);
    await browser.close();
  } catch (e) {}

  process.exit(unlocked ? 0 : 1);
})();
