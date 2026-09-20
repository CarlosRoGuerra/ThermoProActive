import AdminLayout from "@/app/(admin)/layout";
import { SecurityCenter } from "@/features/auth/components/security-center";

export default function AdminSecurityPage() {
  return <AdminLayout><SecurityCenter contexto="admin" /></AdminLayout>;
}
