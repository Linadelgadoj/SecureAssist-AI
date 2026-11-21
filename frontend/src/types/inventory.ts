export type Role = "admin" | "technician";
export type LocationKind = "warehouse" | "vehicle" | "other";
export type EquipmentStatus = "operational" | "in_repair" | "out_of_service" | "removed";
export type RepairStatus = "open" | "in_progress" | "resolved" | "cancelled";
export type ManualMovementReason = "receipt" | "issue" | "adjustment";

export interface Account {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
}

export interface StockAtLocation {
  location_id: string;
  location_name: string;
  location_kind: LocationKind;
  quantity: number;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  brand: string | null;
  model: string | null;
  unit: string;
  min_stock: number;
  description: string | null;
  is_active: boolean;
  total_quantity: number;
  is_low_stock: boolean;
  stock: StockAtLocation[];
}

export interface ProductInput {
  sku: string;
  name: string;
  category: string;
  brand?: string | null;
  model?: string | null;
  unit?: string;
  min_stock?: number;
  description?: string | null;
}

export interface StockLocation {
  id: string;
  name: string;
  kind: LocationKind;
  is_active: boolean;
}

export interface StockMovement {
  id: string;
  product_id: string;
  product_sku: string;
  product_name: string;
  location_id: string;
  location_name: string;
  quantity_delta: number;
  reason: string;
  repair_id: string | null;
  note: string | null;
  created_at: string;
  created_by_email: string;
}

export interface Equipment {
  id: string;
  client_id: string;
  product_id: string | null;
  equipment_type: string;
  brand: string | null;
  model: string | null;
  serial_number: string | null;
  site_description: string | null;
  installed_on: string | null;
  status: EquipmentStatus;
  notes: string | null;
}

export interface EquipmentInput {
  equipment_type: string;
  brand?: string | null;
  model?: string | null;
  serial_number?: string | null;
  site_description?: string | null;
  installed_on?: string | null;
  notes?: string | null;
}

export interface ClientSummary {
  id: string;
  name: string;
  document_id: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  equipment_count: number;
  open_repairs: number;
}

export interface ClientDetail extends Omit<ClientSummary, "equipment_count" | "open_repairs"> {
  equipment: Equipment[];
}

export interface ClientInput {
  name: string;
  document_id?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface RepairSummary {
  id: string;
  client_id: string;
  client_name: string;
  equipment_id: string | null;
  equipment_label: string | null;
  equipment_serial: string | null;
  technician_id: string;
  technician_email: string;
  technician_name: string | null;
  conversation_id: string | null;
  problem_description: string;
  diagnosis: string | null;
  solution: string | null;
  status: RepairStatus;
  opened_at: string;
  closed_at: string | null;
  parts_count: number;
}

export interface RepairDetail extends RepairSummary {
  parts: StockMovement[];
}

export interface EquipmentDetail extends Equipment {
  client_name: string;
  repairs: RepairSummary[];
}
