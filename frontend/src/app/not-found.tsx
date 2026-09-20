import Link from "next/link";
import { Button, Card, Logo } from "@/components/ds";

/** Endereço que não existe — com saída, não com beco sem saída. */
export default function NaoEncontrado() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <Logo tamanho="lg" />
        </div>
        <Card>
          <h1 className="text-lg font-semibold text-fg">Esta página não existe</h1>
          <p className="mt-1.5 text-sm text-fg-muted">
            O endereço pode ter mudado ou o registro foi removido. Volte ao início e tente pelo menu.
          </p>
          <div className="mt-5">
            <Link href="/">
              <Button size="sm">Voltar ao início</Button>
            </Link>
          </div>
        </Card>
      </div>
    </main>
  );
}
