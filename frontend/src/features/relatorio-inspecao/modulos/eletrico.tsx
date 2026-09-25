import type { DossieTransformador, KpisTransformador, Transformador } from "../tipos";
import { STATUS_KPI, StatTile } from "../shell/kpis";
import { Campo, FolhaFicha, Quadro, QuadroCliente, TiposEnsaio } from "./transformador/folha";
import { data, kV, numero, numeroEnxuto, tensaoSecundaria } from "./transformador/formato";
import { criarModuloTransformador } from "./transformador/modulo";

/* Ensaios elétricos de transformador (2025-12_TRF-001_ENDe.pdf): registro dos
   ensaios e as fichas R×T, R×I e R×O. Carta no backend (apps/ensaios/carta.py). */

const ROTULOS_ENSAIO: Record<string, string> = {
  RXT: "R x T [TTR]", RXI: "R x I [Isolação]", RXO: "R x O [Ôhmica]",
};

/** Ficha 1 — Registro de dados dos ensaios elétricos. */
function RegistroEnsaios({ d, t }: { d: DossieTransformador; t: Transformador }) {
  const c = t.cadastro;
  const r = t.registro;
  return (
    <FolhaFicha cab={d.cabecalho} titulo="REGISTRO DE DADOS DOS ENSAIOS ELÉTRICOS">
      <QuadroCliente d={d} />
      <Quadro colunas={4} style={{ marginTop: "4mm" }}>
        <Campo rotulo="Local da Instalação do Equipamento" span={2}>{c.local}</Campo>
        <Campo rotulo="Identificação do Equipamento" span={2}>{c.identificacao}</Campo>
        <Campo rotulo="Número de Série" span={2}>{c.numero_serie}</Campo>
        <Campo rotulo="Número de Patrimônio" span={2}>{c.numero_patrimonio}</Campo>
        <Campo rotulo="Fabricante">{c.fabricante}</Campo>
        <Campo rotulo="Ano de Fabricação">{c.ano_fabricacao ?? ""}</Campo>
        <Campo rotulo="Tipo de Equipamento">{c.tipo_equipamento}</Campo>
        <Campo rotulo="Tipo">{c.modelo}</Campo>
        <Campo rotulo="Potência" unidade="kVA">{numeroEnxuto(c.potencia_kva, 1)}</Campo>
        <Campo rotulo="Tensão Primária" unidade="kV">{kV(c.tensao_primaria_v)}</Campo>
        <Campo rotulo="Tensão Secundária" unidade="V">{tensaoSecundaria(c)}</Campo>
        <Campo rotulo="Tipo de Ligação">{c.grupo_ligacao}</Campo>
        <Campo rotulo="TAP">{r?.tap}</Campo>
        <Campo rotulo="Tensão TAP" unidade="kV">{kV(r?.tensao_tap_v)}</Campo>
        <Campo rotulo="Temperatura do Óleo" unidade="°C">{numero(r?.temperatura_oleo_c, 1)}</Campo>
        <Campo rotulo="Temperatura Ambiente" unidade="°C">{numero(r?.temperatura_ambiente_c, 1)}</Campo>
        <Campo rotulo="Data do Ensaio">{data(r?.data)}</Campo>
        <Campo rotulo="Analista">{r?.analista}</Campo>
        <Campo rotulo="Quantidade de Óleo" unidade="L">{numero(c.volume_oleo_l, 1)}</Campo>
        <Campo rotulo="Umidade Relativa" unidade="%">{numero(r?.umidade_relativa_pct, 1)}</Campo>
        <TiposEnsaio tipos={t.tipos_ensaio} rotulos={ROTULOS_ENSAIO} />
      </Quadro>
    </FolhaFicha>
  );
}

/** Indicadores próprios: pior erro de relação e menor índice de polarização. */
function KpisEletricos({ k }: { k: KpisTransformador }) {
  const erro = k.maior_erro_relacao;
  const limite = k.limite_erro_relacao;
  const foraDoErro = erro != null && limite != null && erro > limite;
  return (
    <div className="flex flex-wrap gap-3">
      <StatTile
        valor={erro != null ? `${numero(erro, 2)} %` : "—"}
        rotulo={`Maior erro de relação (R×T)${limite != null ? ` · admitido ± ${numero(limite, 1)} %` : ""}`}
        cor={foraDoErro ? STATUS_KPI.critical : undefined}
      />
      <StatTile valor={k.menor_ip != null ? numero(k.menor_ip, 2) : "—"} rotulo="Menor índice de polarização (R×I)" />
    </div>
  );
}

export const MODULO_ENSAIO_ELETRICO = criarModuloTransformador({
  chave: "ENSAIO_ELETRICO",
  tituloFichas: "Fichas dos\nEnsaios Elétricos",
  Registro: RegistroEnsaios,
  // Nos elétricos o terceiro quadro é a instrumentação de cada ensaio.
  informacoes: (f) => [f.instrumento, f.informacoes_adicionais].filter(Boolean).join("\n"),
  KpisExtras: KpisEletricos,
});
