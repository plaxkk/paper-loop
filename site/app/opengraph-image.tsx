import { ImageResponse } from 'next/og';
export const alt='Paper Loop — Read the papers that shaped AI';
export const size={width:1200,height:630};
export const contentType='image/png';
export default function Image(){ return new ImageResponse(<div style={{background:'#f6f5f0',color:'#252a28',width:'100%',height:'100%',display:'flex',flexDirection:'column',justifyContent:'center',padding:90}}><div style={{fontSize:26,color:'#536d5b'}}>AI CLASSICS / READING NOTES</div><div style={{fontSize:106,marginTop:28}}>Paper Loop.</div><div style={{fontSize:34,marginTop:30}}>Read the papers that shaped AI.</div><div style={{fontSize:24,marginTop:45,color:'#536d5b'}}>2017 — 2023 · Chinese explanations by kk</div></div>,size); }
