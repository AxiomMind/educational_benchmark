const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const COOKIE_PATH = 'C:/Users/26730/educational_benchmark/data/xkw_cookies.json';

(async () => {
  console.log('>>> 正在启动可视化浏览器登录窗口...');
  const browser = await chromium.launch({
    headless: false,
    args: [
      '--start-maximized',
      '--disable-blink-features=AutomationControlled'
    ]
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 850 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  });

  const page = await context.newPage();
  console.log('>>> 正在打开组卷网首页...');

  try {
    await page.goto('https://zujuan.xkw.com/gzls/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (err) {
    console.log('页面加载提示:', err.message);
  }

  await page.waitForTimeout(2000);

  // 尝试自动触发登录弹窗
  console.log('>>> 正在自动唤起登录弹窗...');
  try {
    await page.evaluate(() => {
      if (typeof logindiv === 'function') {
        logindiv();
      } else {
        const btn = document.querySelector('.login-btn');
        if (btn) btn.click();
      }
    });
    console.log('>>> 登录弹窗已唤起！');
  } catch (e) {
    console.log('唤起登录弹窗提示:', e.message);
  }

  console.log('\n======================================================');
  console.log(' 请在弹出的浏览器窗口中，扫码或验证码登录已充值的 VIP 账号！');
  console.log(' 登录成功后，脚本会自动捕获 VIP 凭证并关闭窗口。');
  console.log('======================================================\n');

  // 轮询检查登录态（最多等待 5 分钟）
  const startTime = Date.now();
  let loggedIn = false;

  while (Date.now() - startTime < 300000) {
    await page.waitForTimeout(2000);

    // 检查 cookies 中是否有学科网登录关键标识
    const cookies = await context.cookies();
    const cookieNames = cookies.map(c => c.name.toLowerCase());

    // 检查页面元素或接口状态
    const pageStatus = await page.evaluate(() => {
      // 检查全局变量或登录用户信息
      if (window.userinfo && Object.keys(window.userinfo).length > 0) return true;
      if (window.isvisitor === false) return true;
      const userBox = document.querySelector('.user-info, .user-name, .logout-btn, a[href*="logout"]');
      if (userBox && userBox.innerText.length > 0) return true;
      return false;
    }).catch(() => false);

    const hasAuthCookie = cookieNames.some(name => 
      name.includes('token') || 
      name.includes('auth') || 
      name.includes('passport') || 
      name.includes('user') ||
      name === 'xkw_user' ||
      name === 'uid'
    );

    if (pageStatus || (hasAuthCookie && cookieNames.length > 8)) {
      // 进一步通过页面请求确认
      console.log('>>> 检测到登录成功信号！正在保存 Cookie...');
      fs.writeFileSync(COOKIE_PATH, JSON.stringify(cookies, null, 2), 'utf8');
      console.log('>>> 🎉 Cookie 已成功保存到:', COOKIE_PATH);
      loggedIn = true;
      break;
    }
  }

  if (!loggedIn) {
    console.log('>>> 扫码登录超时（3分钟）。');
  }

  await page.waitForTimeout(2000);
  await browser.close();
  process.exit(loggedIn ? 0 : 1);
})();
