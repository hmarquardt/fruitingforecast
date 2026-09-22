// Production-data browser tests exercise local hydrated Parquet. Hosting tests
// separately exercise the live remote origin from the GitHub Pages origin.
// Analytics is intercepted here so local tests and CI never send collector
// traffic; domain acceptance is verified separately against production.
const fs=require('fs');
module.exports=function(test){test.beforeEach(async({page})=>{
 await page.route('https://analytics.aismallbizguru.com/**',route=>route.fulfill({status:200,contentType:'application/javascript',body:''}));
 await page.route('**/data/manifest.json*',route=>{
  const manifest=JSON.parse(fs.readFileSync('data/manifest.json','utf8'));
  delete manifest.assetBaseUrl;
  return route.fulfill({contentType:'application/json',body:JSON.stringify(manifest)});
 });
})};