const {chromium}=require(require.resolve('playwright',{paths:['/home/claude/khayyal.alatraf/_tiktok/render','/home/claude/khayyal.alatraf']}));
(async()=>{const b=await chromium.launch();
for(const [n,h,vars] of [['story-qr',1920,'--h:1920px;--pad:130px;--lg:520px;--h1:80px;--g:50px;--g2:44px;--chip:40px;--t:58px;--qw:360px;--ct:38px;--lic:36px;--lm:40px'],['post-qr',1080,'--h:1080px;--pad:44px;--lg:230px;--h1:50px;--g:10px;--g2:14px;--chip:24px;--t:34px;--qw:270px;--ct:24px;--lic:22px;--cp:24px;--lm:14px;--ql:22px']]){
const p=await b.newPage({viewport:{width:1080,height:h}});await p.goto('file://'+__dirname+'/card.html');
await p.evaluate(v=>document.querySelector('.p').setAttribute('style',v),vars);await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(300);
console.log(n,await p.evaluate(()=>{const e=document.querySelector('.lic').getBoundingClientRect();return e.bottom}));await p.screenshot({path:__dirname+'/'+n+'.png'});}
await b.close()})();
