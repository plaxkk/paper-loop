import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
export default defineConfig({testDir:'./tests',timeout:45000,fullyParallel:false,workers:1,use:{baseURL:process.env.PAPER_TEST_URL||'http://localhost:3000',headless:true,launchOptions:{executablePath:process.env.PAPER_CHROME_PATH||(existsSync(chrome)?chrome:undefined)},trace:'retain-on-failure'},reporter:'list'});
