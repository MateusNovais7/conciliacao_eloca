export type Client = {
  id: string;
  name: string;
  created_at: string;
};

export type BankAccount = {
  id: string;
  client_id: string;
  bank: string;
  agency: string | null;
  account_number: string;
  date_tolerance_business_days: number;
  amount_tolerance: number;
  consider_interest: boolean;
  consider_fee_in_settlement: boolean;
  period_cutoff_enabled: boolean;
  separate_anticipations: boolean;
  grouping_enabled: boolean;
};

export type ImportFile = {
  id: string;
  bank_account_id: string;
  kind: "ERP" | "BANK" | "CRP032A1";
  original_filename: string;
  competencia_year: number;
  competencia_month: number;
  period_start: string | null;
  period_end: string | null;
  row_count: number | null;
  imported_by: string | null;
  imported_at: string;
};

export type Reconciliation = {
  id: string;
  bank_account_id: string;
  competencia_year: number;
  competencia_month: number;
  status: "RASCUNHO" | "EM_ANALISE" | "CONCILIADA" | "FECHADA" | "REABERTA";
  created_at: string;
  closed_at: string | null;
  closed_by: string | null;
};

export type DashboardStatusCount = {
  status: string;
  count: number;
  total_amount: number;
};

export type Dashboard = {
  reconciliation_id: string;
  bank_titles_count: number;
  erp_titles_count: number;
  reconciled_count: number;
  reconciled_pct: number;
  reconciled_amount: number;
  divergent_amount: number;
  by_status: DashboardStatusCount[];
};

export type ReconciliationHistoryItem = {
  id: string;
  competencia_year: number;
  competencia_month: number;
  status: string;
  reconciled_pct: number;
  created_at: string;
  closed_at: string | null;
};

export type ReconciliationMatch = {
  id: string;
  status: string;
  confidence: number;
  diagnostic: string | null;
  bank_transaction_id: string | null;
  erp_transaction_id: string | null;
  is_manual_override: boolean;
  ignored: boolean;
};

export type BankTransactionDetail = {
  id: string;
  movement_date: string;
  seu_numero: string | null;
  nosso_numero: string;
  payer_name: string | null;
  operation_type: string | null;
  principal_amount: number | null;
  interest_amount: number;
  fee_amount: number;
  final_amount: number | null;
};

export type ERPTransactionDetail = {
  id: string;
  transaction_date: string;
  invoice_number_raw: string | null;
  nota_fiscal: string | null;
  descricao: string | null;
  incoming_amount: number | null;
  outgoing_amount: number | null;
};

export type DocumentoRecebidoDetail = {
  id: string;
  documento: string;
  cliente: string | null;
  data_pagamento: string | null;
  valor_emissao: number | null;
  valor_desconto: number;
  valor_abatimento: number;
  valor_juros: number;
  valor_multa: number;
  valor_pago: number | null;
};

export type ReconciliationMatchDetail = {
  id: string;
  status: string;
  confidence: number;
  diagnostic: string | null;
  is_manual_override: boolean;
  ignored: boolean;
  bank_transaction: BankTransactionDetail | null;
  erp_transaction: ERPTransactionDetail | null;
  documento_recebido: DocumentoRecebidoDetail | null;
};

