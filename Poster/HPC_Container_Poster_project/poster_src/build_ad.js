const pptxgen = require("pptxgenjs");
const FIG = "/home/claude/poster_src/figures/";
const IMG = "/home/claude/poster_src/images/";
const QR  = "/home/claude/qr-1.png";

const TEAL="0E8C6E", TEALD="0A6F57", MAG="DE0054", WHITE="FFFFFF",
      LIGHT="CFEAE0", INK="14342B";
const shadow = () => ({ type:"outer", color:"000000", blur:9, offset:3, angle:90, opacity:0.22 });

let p = new pptxgen();
p.defineLayout({ name:"W16x9", width:13.333, height:7.5 });
p.layout = "W16x9";
p.author = "Krishna Kant Singh";
p.title  = "Portable HPC Containers for EBRAINS — poster teaser";

let s = p.addSlide();
s.background = { color: TEAL };

// soft deeper-teal panel behind the left text (subtle depth, not a stripe)
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x:-0.4, y:-0.4, w:8.1, h:8.3,
  fill:{ color:TEALD, transparency:35 }, line:{ type:"none" }, rectRadius:0.2 });

// ---- kicker + ESD logo ----
s.addImage({ path: IMG+"ebrains_logo_ESD_sticker_whiteonly.png", x:0.55, y:0.42, w:0.85, h:0.85 });
s.addText("EBRAINS SOFTWARE DISTRIBUTION  ·  POSTER", { x:1.55, y:0.5, w:6.2, h:0.7,
  fontFace:"Calibri", fontSize:14, bold:true, color:LIGHT, charSpacing:2, valign:"middle", margin:0 });

// ---- title ----
s.addText("Run NEST anywhere —\nat native speed", { x:0.55, y:1.25, w:7.1, h:1.7,
  fontFace:"Calibri", fontSize:46, bold:true, color:WHITE, lineSpacingMultiple:0.95, margin:0 });
s.addText("Portable, streaming HPC containers — how much does portability cost?",
  { x:0.6, y:2.95, w:7.0, h:0.5, fontFace:"Calibri", fontSize:19, italic:true, color:LIGHT, margin:0 });

// ---- three stat callouts ----
const stats = [
  { big:"\u22480%", lab:"performance cost\nvs bare-metal" },
  { big:"1 image", lab:"build once, run on\nany EuroHPC site" },
  { big:"native",  lab:"MPI latency & NCCL\nbandwidth, in-container" },
];
const cw=2.28, gap=0.18, x0=0.6, yC=3.75, hC=1.5;
stats.forEach((st,i)=>{
  const x=x0+i*(cw+gap);
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y:yC, w:cw, h:hC,
    fill:{ color:WHITE, transparency:8 }, line:{ type:"none" }, rectRadius:0.09, shadow:shadow() });
  s.addText(st.big, { x:x, y:yC+0.12, w:cw, h:0.6, fontFace:"Calibri", fontSize:30, bold:true,
    color:MAG, align:"center", margin:0 });
  s.addText(st.lab, { x:x, y:yC+0.72, w:cw, h:0.68, fontFace:"Calibri", fontSize:13.5,
    color:INK, align:"center", valign:"top", margin:0, lineSpacingMultiple:0.95 });
});

// ---- method line (pill) ----
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x:0.6, y:5.45, w:6.96, h:0.62,
  fill:{ color:MAG }, line:{ type:"none" }, rectRadius:0.31 });
s.addText("PMIx wire-up   ·   QEMU multi-arch   ·   CernVM-FS streaming",
  { x:0.6, y:5.45, w:6.96, h:0.62, fontFace:"Calibri", fontSize:16.5, bold:true,
    color:WHITE, align:"center", valign:"middle", margin:0 });

// ---- author + CTA + QR (bottom) ----
s.addText([
  { text:"Krishna Kant Singh", options:{ bold:true, fontSize:16, color:WHITE, breakLine:true } },
  { text:"Jülich Supercomputing Centre · Forschungszentrum Jülich", options:{ fontSize:12.5, color:LIGHT } },
], { x:0.62, y:6.35, w:4.5, h:0.9, fontFace:"Calibri", valign:"top", margin:0 });

s.addShape(p.shapes.ROUNDED_RECTANGLE, { x:6.42, y:6.28, w:1.02, h:1.02,
  fill:{ color:WHITE }, line:{ type:"none" }, rectRadius:0.06, shadow:shadow() });
s.addImage({ path:"/home/claude/qr_esd.png", x:6.5, y:6.36, w:0.86, h:0.86 });
s.addText([
  { text:"Visit my poster", options:{ bold:true, fontSize:15, color:WHITE, breakLine:true } },
  { text:"ebrains.eu/esd", options:{ fontSize:12.5, color:LIGHT } },
], { x:4.55, y:6.5, w:1.75, h:0.7, fontFace:"Calibri", align:"right", valign:"middle", margin:0 });

// ================= RIGHT: approach + proof figures in white cards =================
function card(x,y,w,h,img,iw,ih,cap){
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill:{ color:WHITE },
    line:{ type:"none" }, rectRadius:0.08, shadow:shadow() });
  // contain image inside card with padding
  const pad=0.18, capH=0.34;
  const availW=w-2*pad, availH=h-2*pad-capH;
  let dw=availW, dh=dw*ih/iw;
  if(dh>availH){ dh=availH; dw=dh*iw/ih; }
  s.addImage({ path:img, x:x+(w-dw)/2, y:y+pad, w:dw, h:dh });
  s.addText(cap, { x:x+0.1, y:y+h-capH-0.04, w:w-0.2, h:capH, fontFace:"Calibri",
    fontSize:12.5, italic:true, color:"4A5A54", align:"center", valign:"middle", margin:0 });
}
const RX=7.9, RW=4.95;
card(RX,0.55,RW,3.35, FIG+"cvmfs_streaming.png", 1834,1024,
     "Approach: build once · stream the stack · run anywhere");
card(RX,4.05,RW,2.9,  FIG+"res_portability_total.png", 1494,754,
     "Proof: container within ±4% of bare-metal (1–32 nodes)");

// EBRAINS wordmark bottom-right
s.addImage({ path:IMG+"ebrains_with_text.png", x:12.0, y:6.95, w:1.2, h:0.42 });

p.writeFile({ fileName:"/home/claude/poster_ad.pptx" }).then(f=>console.log("saved",f));
