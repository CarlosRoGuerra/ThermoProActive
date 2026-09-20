import { LegalDocument } from "@/features/auth/components/legal-document";

export default function TermosPage() {
  return (
    <LegalDocument
      title="Termos de Uso"
      summary="Estes termos regulam o acesso à plataforma Pred Ativos por clientes, colaboradores e pessoas convidadas por uma organização autorizada."
    >
      <section><h2>1. Acesso autorizado</h2><p>O acesso é pessoal, intransferível e limitado ao perfil e à organização associados à conta. A criação de uma conta depende de aprovação ou convite válido. O usuário deve manter suas credenciais protegidas e comunicar qualquer suspeita de uso indevido.</p></section>
      <section><h2>2. Uso da plataforma</h2><p>A plataforma deve ser usada para atividades legítimas de manutenção preditiva, inspeção, análise e gestão operacional. É proibido tentar contornar controles de acesso, acessar dados de outra organização, interferir no serviço ou inserir conteúdo ilícito.</p></section>
      <section><h2>3. Registros e responsabilidades</h2><p>Ações relevantes podem ser registradas para segurança, auditoria e rastreabilidade. Cada organização é responsável pela exatidão dos dados que fornece e pela gestão dos acessos concedidos aos seus integrantes.</p></section>
      <section><h2>4. Disponibilidade e evolução</h2><p>A ThermoProActive adota medidas razoáveis para manter o serviço seguro e disponível. Manutenções, atualizações ou eventos fora de controle podem causar indisponibilidade temporária. Funcionalidades podem evoluir sem reduzir direitos já contratados.</p></section>
      <section><h2>5. Propriedade e confidencialidade</h2><p>O software, sua identidade visual e seus componentes permanecem protegidos pela legislação aplicável. Dados operacionais e documentos de cada cliente permanecem restritos à organização autorizada e aos prestadores necessários à execução do serviço.</p></section>
      <section><h2>6. Encerramento e documentos contratuais</h2><p>O acesso pode ser suspenso em caso de risco de segurança, uso indevido ou término da relação contratual. Quando houver contrato específico entre as partes, ele prevalecerá sobre estes termos em caso de divergência.</p></section>
    </LegalDocument>
  );
}
