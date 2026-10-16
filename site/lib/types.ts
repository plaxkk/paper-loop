export type Block = { id: string; page: number; text: string; bbox: number[] };
export type PaperPage = { number: number; width: number; height: number; parsed: boolean };
export type Claim = { title: string; explanation: string; category: string; citations: string[] };
export type Overview = { question: string; method: string; results: string; limitations: string; claims: Claim[] };
export type Job = { id: string; kind: string; status: string; result: { translations?: {id:string;text:string}[]; answer?:string; citations?:string[] } | null; error: string | null };
export type Message = { id:string; role:string; content:string; citations:string[]; job:string };
export type Workspace = { id:string; title:string; status:string; error:string|null; analysis_error:string|null; source:string; created:number; page:number; pages:PaperPage[]; blocks:Block[]; overview:Overview|null; jobs:Job[]; messages:Message[]; pdf_available:boolean };
export type Session = { service_available?:boolean; ai_available:boolean; remaining_imports:number; remaining_actions:number; retention_days:number };
