// يحوّل مواصفات فيديو (JSON) إلى MP4 عمودي 1080×1920 بهوية خيال الأطراف.
// الاستخدام: node _tiktok/render/render.js <spec.json> <out.mp4> [fps=30]
// تعليق صوتي: أضف "audio":"../voice/<slug>.mp3" في المواصفات (مسار نسبي لملف المواصفات) فيُدمج تلقائياً.
// يتطلب: playwright (Chromium) و ffmpeg. الصوت: مسار صامت؛ يضيف المالك صوتاً رائجاً من مكتبة تيك توك التجارية عند النشر.
const {chromium}=require('playwright');const {spawn}=require('child_process');const fs=require('fs');const path=require('path');
(async()=>{
 const [specPath,out,fpsArg]=process.argv.slice(2);const fps=+(fpsArg||30);
 const spec=JSON.parse(fs.readFileSync(specPath,'utf8'));
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
 await p.goto('file://'+path.join(__dirname,'template.html'));await p.evaluate(()=>document.fonts.ready);
 const T=await p.evaluate(s=>build(s),spec);await p.waitForTimeout(400);
 const n=Math.round(T*fps);
 const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(fps),'-i','-',...(spec.audio?['-i',path.resolve(path.dirname(specPath),spec.audio),'-af','apad']:['-f','lavfi','-i','anullsrc=r=44100:cl=stereo']),'-shortest','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart',out],{stdio:['pipe','inherit','inherit']});
 for(let i=0;i<n;i++){await p.evaluate(t=>render(t),i/fps);const buf=await p.screenshot({type:'jpeg',quality:92});
  if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r));}
 // غلاف: لحظة اكتمال الخطاف
 const cover=spec.cover_at??Math.min(2.4,spec.scenes[0].dur-.5);await p.evaluate(t=>render(t),cover);
 await p.screenshot({path:out.replace(/\.mp4$/,'-cover.jpg'),type:'jpeg',quality:92});
 ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();
 console.log(`done ${out} ${T.toFixed(1)}s ${n} frames`);
})();
