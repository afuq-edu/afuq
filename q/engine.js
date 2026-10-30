/* ألعاب ونشاط الدرس – منصة أفق.
   Data: window.QZ = {g, gn, s, sn, L:[{t:title, u:unit, q:[[question, answer, level 0|1|2|-1, distractors? | 1 (true/false item)]]}]}
   Page: <subject>/?l=N (1-based lesson). Three games + one activity, 10 points each; each one finished gives its own certificate (canvas → PNG), all four a full one.
   Built from the prep files by tools/build_quiz.py (site repo); this file is copied to afuq-edu/afuq q/engine.js. */
(function(){
'use strict';
var D=window.QZ, app=document.getElementById('app');
var LVN=['معرفة','تطبيق','استدلال'];
var GAMES=[
  {id:'tf',ic:'🚀',n:'صح أم خطأ',d:'اقرأ السؤال والإجابة المقترحة، ثم احكم: صح أم خطأ؟',c:'g1'},
  {id:'bx',ic:'🎁',n:'افتح الصناديق',d:'افتح كل صندوق وأجب عن سؤاله لتربح نجمة',c:'g2'},
  {id:'ct',ic:'🎯',n:'صياد الإجابة',d:'اختر السرعة واصطد الإجابة الصحيحة وهي تسقط من السماء',c:'g3'},
  {id:'mc',ic:'📝',n:'نشاط: اختر الإجابة الصحيحة',d:'عشرة أسئلة بمستويات: معرفة، تطبيق، استدلال',c:'g4'}];
function $(s,r){return (r||document).querySelector(s);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function shuffle(a){a=a.slice();for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1)),t=a[i];a[i]=a[j];a[j]=t;}return a;}
function norm(s){return String(s).replace(/[ً-ْـ‎‏⁦-⁩‪-‮]/g,'').replace(/[إأآا]/g,'ا').replace(/[ىي]/g,'ي').replace(/ة/g,'ه').replace(/[^\w؀-ۿ]+/g,'').toLowerCase();}
function sget(k){try{return localStorage.getItem(k);}catch(e){return null;}}
function sset(k,v){try{if(v==null)localStorage.removeItem(k);else localStorage.setItem(k,v);}catch(e){}}
var AD='٠١٢٣٤٥٦٧٨٩';function ar(n){return String(n).replace(/\d/g,function(d){return AD[d];});}

/* ---------- sound ---------- */
var AC=null,muted=sget('afuq-q-mute')==='1';
function beep(ok){ if(muted) return; try{ AC=AC||new (window.AudioContext||window.webkitAudioContext)(); var t=AC.currentTime;
  (ok?[523,659,784]:[220,175]).forEach(function(f,i){var o=AC.createOscillator(),g=AC.createGain();o.type=ok?'triangle':'sawtooth';o.frequency.value=f;
    g.gain.setValueAtTime(.0001,t+i*.09);g.gain.exponentialRampToValueAtTime(ok?.18:.08,t+i*.09+.02);g.gain.exponentialRampToValueAtTime(.0001,t+i*.09+.22);
    o.connect(g);g.connect(AC.destination);o.start(t+i*.09);o.stop(t+i*.09+.25);}); }catch(e){} }

/* ---------- lesson & item pools ---------- */
var params=new URLSearchParams(location.search), li=parseInt(params.get('l')||D.l,10)-1;   /* D.l: a page made for one lesson (SCORM package) */
if(!D||!D.L||!D.L.length){app.innerHTML='<div class="wrap"><div class="card">لا توجد بيانات.</div></div>';return;}
if(!(li>=0&&li<D.L.length)) return lessonList();
var L=D.L[li], KEY='afuq-q:'+D.g+'/'+D.s+'/'+(li+1);
function items(i){return (D.L[i].q||[]).map(function(x){return {q:x[0],a:x[1],lv:x[2],o:x[3],li:i};});}
var POOL=items(li);
/* a short lesson borrows questions from its neighbours in the same unit (then any neighbour) */
(function(){var k=1;while(POOL.length<8&&k<D.L.length){[li-k,li+k].forEach(function(j){if(j>=0&&j<D.L.length&&POOL.length<8&&(D.L[j].u===L.u||k>2))POOL=POOL.concat(items(j));});k++;}})();
var ALL=null;function allItems(){if(!ALL){ALL=[];D.L.forEach(function(_,i){ALL=ALL.concat(items(i));});}return ALL;}
function isTF(it){return it.o===1;}
function tfTruth(it){return /^\s*(صح|صحيح|صحيحة|صواب|نعم|True|Yes|✔|✓)/i.test(it.a);}
function kind(s){s=String(s);var lat=(s.match(/[A-Za-z]/g)||[]).length,arb=(s.match(/[؀-ۿ]/g)||[]).length,dig=(s.match(/[0-9٠-٩]/g)||[]).length;
  return (lat>arb?'L':'A')+(dig>=Math.max(1,(s.replace(/\s/g,'').length)/3)?'9':'');}
/* k wrong answers for an item: its own printed options first, then answers of similar shape from the lesson, unit, subject */
function distract(it,k){
  if(isTF(it)) return /^\s*(True|False)/i.test(it.a)?[tfTruth(it)?'False':'True']:[tfTruth(it)?'خطأ':'صح'];
  var out=[],seen={},ca=norm(it.a);seen[ca]=1;
  function add(s){var n=norm(s);if(!n||seen[n]||n.indexOf(ca)>=0&&ca.length>3||ca.indexOf(n)>=0&&n.length>3)return;seen[n]=1;out.push(s);}
  if(Array.isArray(it.o)) shuffle(it.o).forEach(function(s){if(out.length<k)add(s);});
  var kd=kind(it.a),la=it.a.length;
  function rank(list){return shuffle(list).filter(function(x){return x!==it&&!isTF(x);}).map(function(x){
    var r=Math.min(la,x.a.length)/Math.max(la,x.a.length);return {a:x.a,s:(kind(x.a)===kd?1:0)+r+(x.li===it.li?.4:0)};}).sort(function(a,b){return b.s-a.s;});}
  [POOL,allItems().filter(function(x){return D.L[x.li].u===L.u;}),allItems()].forEach(function(src){
    if(out.length>=k) return; rank(src).forEach(function(x){if(out.length<k)add(x.a);});});
  return out;
}
/* n rounds from the pool: every item once before any repeats; optional preference (e.g. short answers) */
function rounds(n,pref){
  var base=POOL.slice(); if(pref){var p=base.filter(pref);if(p.length>=Math.min(n,6))base=p;}
  var out=[];while(out.length<n){out=out.concat(shuffle(base));}
  return out.slice(0,n);
}
function balanced(n){ /* the activity: mix of levels */
  var by=[[],[],[],[]];shuffle(POOL).forEach(function(x){by[x.lv>=0&&x.lv<=2?x.lv:3].push(x);});
  var out=[],i=0;while(out.length<n&&(by[0].length||by[1].length||by[2].length||by[3].length)){var b=by[i%4];if(b.length)out.push(b.shift());i++;}
  if(out.length<n) out=out.concat(rounds(n-out.length));
  return out.slice(0,n).sort(function(a,b){return (a.lv<0?1:a.lv)-(b.lv<0?1:b.lv);});
}
function short(s,max){s=String(s).trim();max=max||46;if(s.length<=max)return s;
  var m=s.split(/[،؛;:.(]|\s[-–—]\s/)[0].trim();if(m.length>=4&&m.length<=max)return m;
  var w=s.split(/\s+/),o='';for(var i=0;i<w.length;i++){if((o+' '+w[i]).trim().length>max-1)break;o=(o+' '+w[i]).trim();}return (o||s.slice(0,max-1))+'…';}

/* ---------- progress ---------- */
var ST={};try{ST=JSON.parse(sget(KEY)||'{}')||{};}catch(e){ST={};}
/* every score change is announced (afuq-q event) — the SCORM package (tools/build_scorm.py) passes it to the LMS */
/* the pupil may finish any one game: done = at least one finished, max = 10 per finished game (score = their average) */
function emit(t){try{window.dispatchEvent(new CustomEvent('afuq-q',{detail:{type:t,key:KEY,st:ST,total:total(),max:Math.max(1,doneN())*10,done:doneN()>0,all:allDone()}}));}catch(e){}}
function save(){sset(KEY,JSON.stringify(ST));emit('score');}
var NAME=sget('afuq-q-name')||'', GIRL=sget('afuq-q-girl')==='1';

/* ---------- screens ---------- */
function header(){
  return '<div class="top"><div class="in"><div class="bar"><span class="sj">'+esc(D.sn)+' · الصف '+esc(D.gn)+'</span>'+
   '<span><button id="mu" type="button" title="الصوت">'+(muted?'🔇':'🔊')+'</button> <button id="hm" type="button">🏠 الرئيسية</button></span></div><h1 class="bdi">'+esc(L.t)+'</h1></div></div>';
}
function bindHome(){var b=$('#hm');if(b)b.onclick=home;var m=$('#mu');if(m)m.onclick=function(){muted=!muted;sset('afuq-q-mute',muted?'1':null);m.textContent=muted?'🔇':'🔊';};}
function total(){var t=0;GAMES.forEach(function(g){t+=ST[g.id]||0;});return t;}
function allDone(){return GAMES.every(function(g){return ST[g.id]!=null;});}
function doneN(){return GAMES.filter(function(g){return ST[g.id]!=null;}).length;}
function cname(g){return g.id==='mc'?'النشاط':g.n;}
function home(){
  window.scrollTo(0,0);
  var h=header()+'<div class="wrap">';
  h+='<div class="card"><h2>👋 مرحبًا بك! تعليمات للطالب</h2><ol class="steps">'+
     '<li>اكتب اسمك في المربع أدناه، فهو يظهر في شهادتك.</li>'+
     '<li>اختر <b>أي لعبة تريدها</b> أو النشاط، ولكلٍّ منها <b>١٠ درجات</b> و<b>شهادة خاصة بها</b>؛ لست مضطرًا لإنهاء الأربعة.</li>'+
     '<li>اقرأ كل سؤال بتمعّن قبل أن تجيب. تُحسب المحاولة الأولى لكل لعبة في الشهادة.</li>'+
     '<li>بعد إنهاء أي لعبة تظهر <b>شهادتك</b> فيها، ومن ينهي الأربعة يحصل أيضًا على الشهادة الكاملة. احفظها صورة وأرسلها لمعلمك.</li></ol>'+
     '<div style="margin-top:10px"><label class="nm" for="nm">✏️ اكتب اسمك كما تريده في الشهادة</label><input class="nm" id="nm" autocomplete="name" maxlength="40" placeholder="الاسم الثلاثي" value="'+esc(NAME)+'">'+
     '<div class="sx"><button type="button" data-g="0" class="'+(GIRL?'':'on')+'">👦 طالب</button><button type="button" data-g="1" class="'+(GIRL?'on':'')+'">👧 طالبة</button></div><div class="warn" id="wn"></div></div></div>';
  if(L.o&&L.o.length) h+='<div class="card"><h2>🎯 مخرجات الدرس التي تقيسها الأنشطة</h2><ul class="outc">'+L.o.map(function(o){return '<li class="bdi">'+esc(o)+'</li>';}).join('')+'</ul></div>';
  h+='<div class="games">'+GAMES.map(function(g,i){var s=ST[g.id];
     return '<button type="button" class="g '+g.c+(s!=null?' done':'')+'" data-i="'+i+'"><span class="ic">'+g.ic+'</span><b>'+g.n+'</b><small>'+g.d+'</small><span class="st">'+(s!=null?'✔ '+ar(s)+' / ١٠':'ابدأ ←')+'</span></button>';}).join('')+'</div>';
  var dn=doneN();
  if(dn) h+='<div class="tot">مجموعك: '+ar(total())+' / '+ar(dn*10)+'</div>';
  h+='<div class="certs" style="margin-top:12px;display:grid;gap:10px">'+(dn?GAMES.filter(function(g){return ST[g.id]!=null;}).map(function(g){
       return '<button type="button" class="big gold ce" data-c="'+g.id+'">🏅 شهادة «'+cname(g)+'» ('+ar(ST[g.id])+' / ١٠)</button>';}).join('')+
     (allDone()?'<button type="button" class="big gold ce" data-c="">🏆 الشهادة الكاملة ('+ar(total())+' / ٤٠)</button>':''):
     '<button type="button" class="big gold" disabled>🏅 أنهِ أي لعبة لتظهر شهادتها</button>')+'</div>';
  if(Object.keys(ST).length) h+='<button type="button" class="link" id="rs">ابدأ من جديد (يمسح الدرجات)</button>';
  h+='</div>';
  app.innerHTML=h;bindHome();
  Array.prototype.forEach.call(document.querySelectorAll('.sx button'),function(b){b.onclick=function(){GIRL=b.getAttribute('data-g')==='1';sset('afuq-q-girl',GIRL?'1':null);
    Array.prototype.forEach.call(document.querySelectorAll('.sx button'),function(x){x.classList.toggle('on',x===b);});};});
  var nm=$('#nm');nm.oninput=function(){NAME=nm.value.replace(/\s+/g,' ').trimStart();sset('afuq-q-name',NAME.trim()||null);$('#wn').textContent='';};
  Array.prototype.forEach.call(document.querySelectorAll('.g'),function(b){b.onclick=function(){
    if(!NAME.trim()){$('#wn').textContent='اكتب اسمك أولًا ثم اختر اللعبة.';nm.focus();return;}
    var g=GAMES[+b.getAttribute('data-i')];
    if(ST[g.id]!=null){ if(!confirm('أنهيت هذه اللعبة ('+ar(ST[g.id])+' / ١٠). هل تريد اللعب مرة أخرى للتدريب؟ درجتك الأولى تبقى في الشهادة.')) return; play(g,true); }
    else play(g,false);
  };});
  Array.prototype.forEach.call(document.querySelectorAll('.ce'),function(b){b.onclick=function(){if(!NAME.trim()){$('#wn').textContent='اكتب اسمك أولًا.';nm.focus();return;}
    var id=b.getAttribute('data-c');cert(id?GAMES.filter(function(g){return g.id===id;})[0]:null);};});
  var rs=$('#rs');if(rs)rs.onclick=function(){if(confirm('مسح كل الدرجات والبدء من جديد؟')){ST={};save();home();}};
}
function finish(g,score,practice){
  if(!practice&&ST[g.id]==null){ST[g.id]=score;save();}
  window.scrollTo(0,0);
  var face=score>=9?'🏆':score>=7?'🌟':score>=5?'👍':'💪';
  var msg=score>=9?'ممتاز! أداء رائع':score>=7?'أحسنت! أداء جيد جدًا':score>=5?'جيد، واصل التقدّم':'لا بأس، راجع الدرس وستتحسن';
  app.innerHTML=header()+'<div class="wrap"><div class="card res"><div class="ic">'+face+'</div><h2>'+g.n+'</h2><div class="sc">'+ar(score)+' / ١٠</div><p>'+msg+'</p>'+
    (practice?'<p class="hint">هذه محاولة تدريب، ودرجتك الأولى ('+ar(ST[g.id])+') هي التي في الشهادة.</p>':'')+
    '<div class="row2"><button type="button" class="big gold" id="cg">🏅 شهادتي في «'+cname(g)+'»</button><button type="button" class="big" id="bk">'+(allDone()?'🏆 الشهادة الكاملة':'اختر لعبة أخرى ←')+'</button></div></div></div>';
  bindHome();$('#cg').onclick=function(){cert(g);};$('#bk').onclick=function(){allDone()?cert():home();};
}
function play(g,practice){window.scrollTo(0,0);({tf:gameTF,bx:gameBoxes,ct:gameCatch,mc:gameMC})[g.id](g,practice);}
function dots(res,cur){var h='<div class="dots">';for(var i=0;i<10;i++)h+='<i class="'+(res[i]===1?'ok':res[i]===0?'no':'')+(i===cur?' cur':'')+'"></i>';return h+'</div>';}
function gh(g,score,k){return '<div class="gh"><span class="t">'+g.ic+' '+g.n+'</span><span class="pill sc">⭐ '+ar(score)+'</span></div>';}
function lvTag(it){return it.lv>=0&&it.lv<=2?'<span class="lv lv'+it.lv+'">'+LVN[it.lv]+'</span><br>':'';}

/* ---------- 1. true / false (rocket) ---------- */
function gameTF(g,practice){
  var R=rounds(10),i=0,score=0,res=[];
  function show(){
    var it=R[i],tf=isTF(it),truth,prop;
    if(tf){truth=tfTruth(it);}else{truth=Math.random()<.5;var w=distract(it,1);if(!w.length)truth=true;prop=truth?it.a:w[0];}
    var pos=8+score*((100-24)/10);
    app.innerHTML=header()+'<div class="wrap">'+gh(g,score)+
      '<div class="rk"><span class="pl">🪐</span><div class="trk"></div><span class="ro" id="ro" style="right:'+pos+'%">🚀</span></div>'+dots(res,i)+
      '<div class="q bdi" id="qq">'+(tf?'<span class="lv lv1">صح أم خطأ؟</span><br>':'')+esc(it.q)+
      (tf?'':'<div class="prop bdi"><span>الإجابة المقترحة:</span>'+esc(prop)+'</div>')+'</div>'+
      '<div class="tfb"><button type="button" class="y" data-v="1">✔ صح</button><button type="button" class="n" data-v="0">✖ خطأ</button></div>'+
      '<div class="fb" id="fb"></div><div id="nx"></div></div>';
    bindHome();
    Array.prototype.forEach.call(document.querySelectorAll('.tfb button'),function(b){b.onclick=function(){
      var ok=(b.getAttribute('data-v')==='1')===truth;Array.prototype.forEach.call(document.querySelectorAll('.tfb button'),function(x){x.disabled=true;x.style.opacity=x===b?1:.45;});
      res[i]=ok?1:0;if(ok)score++;beep(ok);
      var fb=$('#fb');fb.className='fb '+(ok?'ok':'no');
      fb.innerHTML=(ok?'✔ إجابتك صحيحة! الصاروخ يتقدم 🚀':'✖ إجابتك غير صحيحة.')+(tf?'<span class="ans bdi">الصواب: '+esc(it.a)+'</span>':(!truth||!ok?'<span class="ans bdi">الإجابة الصحيحة: '+esc(it.a)+'</span>':''));
      if(ok){$('#ro').style.right=(8+score*((100-24)/10))+'%';}else $('#qq').classList.add('shake');
      $('#nx').innerHTML='<button type="button" class="big next" id="nb">'+(i<9?'السؤال التالي ←':'النتيجة 🏁')+'</button>';
      $('#nb').onclick=function(){i++;if(i<10)show();else finish(g,score,practice);};
    };});
  }
  show();
}

/* ---------- 2. open the boxes ---------- */
function gameBoxes(g,practice){
  var R=rounds(10),open=[],score=0,cnt=0;
  function grid(){
    window.scrollTo(0,0);
    var h=header()+'<div class="wrap">'+gh(g,score)+'<div class="card" style="margin-top:4px">🎁 اضغط أي صندوق مغلق لتظهر لك أسئلته. الإجابة الصحيحة تكسبك ⭐.</div><div class="boxes">';
    for(var k=0;k<10;k++){var o=open[k];h+=o==null?'<button type="button" class="bx" data-k="'+k+'"><small>'+ar(k+1)+'</small>🎁</button>':'<div class="bx op'+(o?'':' no')+'">'+(o?'⭐':'💨')+'</div>';}
    app.innerHTML=h+'</div></div>';bindHome();
    Array.prototype.forEach.call(document.querySelectorAll('button.bx'),function(b){b.onclick=function(){ask(+b.getAttribute('data-k'));};});
  }
  function ask(k){
    window.scrollTo(0,0);
    var it=R[k],opts=shuffle([it.a].concat(distract(it,isTF(it)?1:2)));
    app.innerHTML=header()+'<div class="wrap">'+gh(g,score)+'<div class="q bdi"><span class="lv lv1">الصندوق '+ar(k+1)+'</span><br>'+esc(it.q)+'</div><div class="opts">'+
      opts.map(function(o,j){return '<button type="button" data-j="'+j+'" class="bdi"><i>'+'أبجد'[j]+'</i><span>'+esc(o)+'</span></button>';}).join('')+'</div><div class="fb" id="fb"></div><div id="nx"></div></div>';
    bindHome();
    Array.prototype.forEach.call(document.querySelectorAll('.opts button'),function(b){b.onclick=function(){
      var j=+b.getAttribute('data-j'),ok=opts[j]===it.a;
      Array.prototype.forEach.call(document.querySelectorAll('.opts button'),function(x){x.disabled=true;if(opts[+x.getAttribute('data-j')]===it.a)x.classList.add('ok');});
      if(!ok)b.classList.add('no');beep(ok);open[k]=ok?1:0;if(ok)score++;cnt++;
      var fb=$('#fb');fb.className='fb '+(ok?'ok':'no');fb.innerHTML=ok?'⭐ أحسنت! ربحت نجمة.':'💨 الصندوق فارغ هذه المرة.<span class="ans bdi">الإجابة الصحيحة: '+esc(it.a)+'</span>';
      $('#nx').innerHTML='<button type="button" class="big next" id="nb">'+(cnt<10?'إلى الصناديق ←':'النتيجة 🏁')+'</button>';
      $('#nb').onclick=function(){cnt<10?grid():finish(g,score,practice);};
    };});
  }
  grid();
}

/* ---------- 3. answer catcher ---------- */
function gameCatch(g,practice){
  var SP=[{ic:'🐢',n:'بطيء',t:11},{ic:'🐇',n:'متوسط',t:7.5},{ic:'🚀',n:'سريع',t:5}];
  app.innerHTML=header()+'<div class="wrap">'+gh(g,0)+'<div class="card"><h2>🎯 كيف تلعب؟</h2>يظهر السؤال في الأعلى، وتسقط الإجابات من السماء بالمظلات. '+
    '<b>واحدة فقط صحيحة</b>؛ اضغط عليها لتصطادها. بعد كل صيد (صحيح أو خطأ) يتغير السؤال، وإن سقطت الإجابات كلها دون صيد يُحسب السؤال خطأ.</div>'+
    '<div class="card"><h2>اختر السرعة</h2><div class="spd">'+SP.map(function(s,i){return '<button type="button" data-i="'+i+'"><span class="ic">'+s.ic+'</span>'+s.n+'</button>';}).join('')+'</div></div></div>';
  bindHome();
  Array.prototype.forEach.call(document.querySelectorAll('.spd button'),function(b){b.onclick=function(){start(SP[+b.getAttribute('data-i')]);};});
  function start(sp){
    var R=rounds(10,function(x){return x.a.length<=46;}),i=0,score=0,res=[],raf=0,busy=false,live=[];
    app.innerHTML=header()+'<div class="wrap">'+gh(g,0).replace('pill sc"','pill sc" id="scp"')+'<div id="dt"></div><div class="q bdi" id="qq"></div><div class="sky" id="sky">'+
      '<span class="cl" style="top:8%;right:6%">☁️</span><span class="cl" style="top:22%;left:10%">☁️</span><span class="cl" style="top:52%;right:30%;font-size:1.8rem">☁️</span><div class="grass"></div></div></div>';
    bindHome();
    var sky=$('#sky');
    function stop(){cancelAnimationFrame(raf);live.forEach(function(x){x.el.remove();});live=[];}
    function next(){stop();i++;if(i<10)round();else{finish(g,score,practice);}}
    function say(t){var m=document.createElement('div');m.className='msg bdi';m.innerHTML=t;sky.appendChild(m);setTimeout(function(){m.remove();},1300);}
    function round(){
      busy=false;var it=R[i];
      $('#qq').innerHTML=lvTag(it)+esc(it.q);$('#dt').innerHTML=dots(res,i);$('#scp').textContent='⭐ '+ar(score);
      var right=short(it.a),wr=distract(it,isTF(it)?1:3).map(function(x){return short(x);}).filter(function(x){return norm(x)!==norm(right);});
      var seen={},ans=[{t:right,ok:1}].concat(wr.map(function(t){return {t:t,ok:0};})).filter(function(x){var n=norm(x.t);if(seen[n])return false;seen[n]=1;return true;});
      ans=shuffle(ans);
      var H=sky.clientHeight,W=sky.clientWidth,dur=sp.t*1000,t0=performance.now();
      live=ans.map(function(a,k){
        var el=document.createElement('div');el.className='bub bdi';el.textContent=a.t;sky.appendChild(el);
        var col=k%2, left=col?W*.52:W*.02; el.style.left=left+'px';
        var h=el.offsetHeight, delay=k*dur*.22, y0=-h-30-(k>1?20:0);
        var o={el:el,a:a,delay:delay,y0:y0,h:h,gone:false};
        el.style.transform='translateY('+y0+'px)';
        el.onpointerdown=function(e){e.preventDefault();hit(o);};
        return o;});
      function frame(now){
        var t=now-t0,any=false;
        live.forEach(function(o){if(o.gone)return;var p=(t-o.delay)/dur;if(p<0){any=true;return;}
          var y=o.y0+p*(H+o.h+40);o.el.style.transform='translateY('+y+'px)';if(y>H){o.gone=true;o.el.remove();}else any=true;});
        if(busy) return;
        if(!any){busy=true;res[i]=0;beep(false);say('⏰ فاتتك الإجابة!<br><small>الصحيحة: '+esc(right)+'</small>');setTimeout(next,1500);return;}
        raf=requestAnimationFrame(frame);
      }
      raf=requestAnimationFrame(frame);
      function hit(o){
        if(busy||o.gone)return;busy=true;cancelAnimationFrame(raf);
        var ok=!!o.a.ok;res[i]=ok?1:0;if(ok)score++;beep(ok);
        o.el.classList.add(ok?'ok':'no');
        live.forEach(function(x){if(x!==o){if(x.a.ok){x.el.classList.add('ok');}else x.el.classList.add('gone');}});
        $('#scp').textContent='⭐ '+ar(score);
        say(ok?'🎯 صيد موفق!':'❌ ليست هذه<br><small>الصحيحة: '+esc(right)+'</small>');
        setTimeout(next,ok?1100:1900);
      }
    }
    round();
  }
}

/* ---------- 4. activity: multiple choice ---------- */
function gameMC(g,practice){
  var R=balanced(10),i=0,score=0,res=[];
  function show(){
    window.scrollTo(0,0);
    var it=R[i],opts=shuffle([it.a].concat(distract(it,isTF(it)?1:3)));
    app.innerHTML=header()+'<div class="wrap">'+gh(g,score)+dots(res,i)+'<div class="q bdi">'+lvTag(it)+'<small style="color:var(--mute);font-weight:400">السؤال '+ar(i+1)+' من ١٠</small><br>'+esc(it.q)+'</div><div class="opts">'+
      opts.map(function(o,j){return '<button type="button" data-j="'+j+'" class="bdi"><i>'+'أبجد'[j]+'</i><span>'+esc(o)+'</span></button>';}).join('')+'</div><div class="fb" id="fb"></div><div id="nx"></div></div>';
    bindHome();
    Array.prototype.forEach.call(document.querySelectorAll('.opts button'),function(b){b.onclick=function(){
      var j=+b.getAttribute('data-j'),ok=opts[j]===it.a;
      Array.prototype.forEach.call(document.querySelectorAll('.opts button'),function(x){x.disabled=true;if(opts[+x.getAttribute('data-j')]===it.a)x.classList.add('ok');});
      if(!ok)b.classList.add('no');beep(ok);res[i]=ok?1:0;if(ok)score++;
      var fb=$('#fb');fb.className='fb '+(ok?'ok':'no');fb.innerHTML=ok?'✔ إجابة صحيحة، أحسنت!':'✖ إجابة غير صحيحة.<span class="ans bdi">الإجابة الصحيحة: '+esc(it.a)+'</span>';
      $('#nx').innerHTML='<button type="button" class="big next" id="nb">'+(i<9?'السؤال التالي ←':'النتيجة 🏁')+'</button>';
      $('#nb').onclick=function(){i++;if(i<10)show();else finish(g,score,practice);};
    };});
  }
  show();
}

/* ---------- certificate ---------- */
function cert(one){   /* one: a game → its own certificate; none → the full one (all four) */
  window.scrollTo(0,0);emit('cert');
  app.innerHTML=header()+'<div class="wrap"><div class="card cert" id="cw"><p class="hint">جارٍ تجهيز الشهادة…</p></div></div>';bindHome();
  var fonts=document.fonts?Promise.all([document.fonts.load('700 40px Taj'),document.fonts.load('400 30px Taj')]).catch(function(){}):Promise.resolve();
  fonts.then(draw);
  function draw(){
    var W=1600,H=1130,c=document.createElement('canvas');c.width=W;c.height=H;var x=c.getContext('2d');
    var F='Taj,Tahoma,sans-serif',tot=one?(ST[one.id]||0):total(),mx=one?10:40,pc=Math.round(tot/mx*100);
    var g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#FFFDF6');g.addColorStop(1,'#F2FAF8');x.fillStyle=g;x.fillRect(0,0,W,H);
    x.strokeStyle='#C99A2E';x.lineWidth=14;x.strokeRect(30,30,W-60,H-60);x.strokeStyle='#1F7A7A';x.lineWidth=4;x.strokeRect(56,56,W-112,H-112);
    ['⭐','⭐','⭐','⭐'].forEach(function(s,k){x.font='46px '+F;x.textAlign='center';x.fillText(s,k%2?W-110:110,k<2?125:H-90);});
    x.direction='rtl';x.textAlign='center';x.fillStyle='#1F7A7A';
    x.font='700 34px '+F;x.fillText('منصة أفق التعليمية',W/2,140);
    x.fillStyle='#B27A00';x.font='700 84px '+F;x.fillText('شهادة إنجاز',W/2,245);
    x.fillStyle='#22313A';x.font='400 34px '+F;x.fillText(GIRL?'تُمنح هذه الشهادة للطالبة':'تُمنح هذه الشهادة للطالب',W/2,320);
    x.fillStyle='#1F7A7A';x.font='700 66px '+F;x.fillText(NAME.trim()||'—',W/2,405);
    x.strokeStyle='#E3C77A';x.lineWidth=3;x.beginPath();x.moveTo(W/2-330,430);x.lineTo(W/2+330,430);x.stroke();
    x.fillStyle='#22313A';x.font='400 32px '+F;x.fillText(one?(GIRL?'لإنجازها '+(one.id==='mc'?'نشاط':'لعبة')+' «'+cname(one)+'» في درس:':'لإنجازه '+(one.id==='mc'?'نشاط':'لعبة')+' «'+cname(one)+'» في درس:'):(GIRL?'لإنجازها ألعاب ونشاط درس:':'لإنجازه ألعاب ونشاط درس:'),W/2,488);
    x.font='700 40px '+F;var t=L.t;while(x.measureText('«'+t+'»').width>W-260&&t.length>8)t=t.slice(0,-2);if(t!==L.t)t+='…';
    x.fillText('«'+t+'»',W/2,545);
    x.font='400 30px '+F;x.fillStyle='#5E7680';x.fillText(D.sn+' – الصف '+D.gn,W/2,595);
    var cw=300,gap=26,x0=W/2+2*cw+1.5*gap-cw/2-cw*0; var cells=GAMES.map(function(gm){return [gm.ic+' '+gm.n.replace('نشاط: ',''),ST[gm.id]||0];});
    cells[3][0]='📝 النشاط';
    if(one){cells=[[one.ic+' '+cname(one),tot]];cw=460;}
    cells.forEach(function(cl,k){var cx=one?W/2:W/2+(1.5-k)*(cw+gap);x.fillStyle='#FFFFFF';x.strokeStyle='#D9E6EC';x.lineWidth=3;
      roundRect(x,cx-cw/2,630,cw,150,22);x.fill();x.stroke();
      x.fillStyle='#22313A';x.font='700 28px '+F;x.fillText(cl[0],cx,685);
      x.fillStyle='#1F7A7A';x.font='700 48px '+F;x.fillText(ar(cl[1])+' / ١٠',cx,752);});
    x.fillStyle='#B27A00';x.font='700 50px '+F;x.fillText((one?'الدرجة: ':'المجموع: ')+ar(tot)+' / '+ar(mx)+'  ('+ar(pc)+'٪)',W/2,860);
    var msg=pc>=90?'ممتاز! أداء رائع، بارك الله فيك 🌟':pc>=75?'أحسنت! أداء جيد جدًا 👏':pc>=50?(GIRL?'جيد، واصلي التدريب لتتقدمي 👍':'جيد، واصل التدريب لتتقدم 👍'):(GIRL?'راجعي الدرس وحاولي مرة أخرى، أنتِ قادرة 💪':'راجع الدرس وحاول مرة أخرى، أنت قادر 💪');
    x.fillStyle='#22313A';x.font='400 36px '+F;x.fillText(msg,W/2,925);
    var d=new Date(),ds;try{ds=d.toLocaleDateString('ar-OM',{weekday:'long',year:'numeric',month:'long',day:'numeric'})+' – '+d.toLocaleTimeString('ar-OM',{hour:'2-digit',minute:'2-digit'});}catch(e){ds=d.toLocaleString();}
    x.fillStyle='#5E7680';x.font='400 28px '+F;x.fillText('التاريخ: '+ds,W/2,1000);
    var url;try{url=c.toDataURL('image/png');}catch(e){url='';}
    var fn='شهادة-'+((NAME.trim()||'طالب')+(one?' '+cname(one):'')).replace(/\s+/g,'-')+'.png';
    $('#cw').innerHTML='<img alt="شهادة الإنجاز" src="'+url+'"><div class="row2"><a class="big" style="text-align:center;text-decoration:none" id="dl" download="'+esc(fn)+'" href="'+url+'">⬇️ حفظ الشهادة</a>'+
      '<button type="button" class="big gold" id="sh">📤 مشاركة</button></div><p class="hint">على الجوال يمكنك أيضًا الضغط مطولًا على الشهادة ثم «حفظ الصورة»، أو تصوير الشاشة. أرسلها لمعلمك.</p>'+
      '<button type="button" class="link" id="bk">← العودة إلى الألعاب والشهادات الأخرى</button>';
    $('#bk').onclick=home;
    $('#sh').onclick=function(){
      if(navigator.share&&navigator.canShare&&url){fetch(url).then(function(r){return r.blob();}).then(function(b){var f=new File([b],fn,{type:'image/png'});
        if(navigator.canShare({files:[f]}))return navigator.share({files:[f],title:'شهادة إنجاز',text:NAME+' – '+L.t+(one?' – '+cname(one):'')+' – '+ar(tot)+'/'+ar(mx)});throw 0;}).catch(function(){window.print();});}
      else window.print();
    };
  }
  function roundRect(x,a,b,w,h,r){x.beginPath();x.moveTo(a+r,b);x.arcTo(a+w,b,a+w,b+h,r);x.arcTo(a+w,b+h,a,b+h,r);x.arcTo(a,b+h,a,b,r);x.arcTo(a,b,a+w,b,r);x.closePath();}
}

/* ---------- lesson list (no ?l) ---------- */
function lessonList(){
  var h='<div class="top"><div class="in"><div class="sj">منصة أفق التعليمية</div><h1>ألعاب ونشاط الدروس – '+esc(D.sn)+' – الصف '+esc(D.gn)+'</h1></div></div><div class="wrap"><div class="card"><h2>اختر الدرس</h2>',u=null;
  D.L.forEach(function(l,i){if(l.u&&l.u!==u){if(u!==null)h+='</ul>';u=l.u;h+='<div class="uh bdi">'+esc(u)+'</div><ul class="ul">';}else if(u===null){u='';h+='<ul class="ul">';}
    h+='<li><a class="bdi" href="?l='+(i+1)+'">'+esc(l.t)+'</a></li>';});
  app.innerHTML=h+'</ul></div></div>';
}

home();
})();
