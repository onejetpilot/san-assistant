import AdminStatus from '../../components/admin/AdminStatus';

export default function AdminPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8">
      <div className="mx-auto max-w-6xl">
        <AdminStatus />
      </div>
    </main>
  );
}
