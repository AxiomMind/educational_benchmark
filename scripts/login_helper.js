const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const COOKIE_PATH = 'C:/Users/26730/educational_benchmark/data/xkw_cookies.json';

(async () => {
  console.log('>>> 正在启动登录窗口，请稍候...');
  const browser = await chromium.launch({
    headless: false,
    proxy: { server: 'http://127.0.0.1:18888' },
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
    await page.goto('https://zujuan.xkw.com/gzls/', { waitUntil: 'load', timeout: 30000 });
  } catch (err) {
    console.log('页面加载提示:', err.message);
  }

  await page.waitForTimeout(3000);

  // 尝试自动触发登录弹窗
  console.log('>>> 正在尝试唤起登录窗口...');
  try {
    const loginBtn = await page.$('.login-btn, a:has-text("登录")');
    if (loginBtn) {
      await loginBtn.click();
      console.log('>>> 已点击登录按钮！');
    } else {
      await page.evaluate(() => {
        if (typeof logindiv === 'function') logindiv();
      });
      console.log('>>> 已执行 logindiv()！');
    }
  } catch (e) {
    console.log('点击登录异常:', e.message);
  }

  console.log('\n======================================================');
  console.log(' 请在弹出的浏览器窗口中，使用微信扫码完成登录！');
  console.log(' 登录完成后脚本会自动捕获 Cookie 并关闭窗口。');
  console.log('======================================================\n');

  // 轮询检查登录态（最多等待 3 分钟）
  const startTime = Date.now();
  let loggedIn = false;

  while (Date.now() - startTime < 180000) {
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
