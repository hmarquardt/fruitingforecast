// Production-data browser tests exercise local hydrated Parquet. Hosting tests
// separately exercise the live remote origin from the GitHub Pages origin.
const fs=require('fs');
module.exports=function(test){test.beforeEach(async({page})=>{
 await page.route('**/data/manifest.json*',route=>{
  const manifest=JSON.parse(fs.readFileSync('data/manifest.json','utf8'));
  delete manifest.assetBaseUrl;
  return route.fulfill({contentType:'application/json',body:JSON.stringify(manifest)});
 });
})};
