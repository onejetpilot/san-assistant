import { Thread } from '../components/assistant-ui/thread';
import { MyRuntimeProvider } from './MyRuntimeProvider';

export default function Page() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-100 via-zinc-100 to-slate-200">
      <MyRuntimeProvider>
        <Thread />
      </MyRuntimeProvider>
    </main>
  );
}
