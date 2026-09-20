import Link from "next/link";
import { LegalDocument } from "@/features/auth/components/legal-document";

export default function PrivacidadePage() {
  return (
    <LegalDocument
      title="Política de Privacidade"
      summary="Esta política explica, de forma resumida, como dados pessoais são tratados no acesso e na operação da plataforma Pred Ativos."
    >
      <section><h2>1. Papéis no tratamento</h2><p>A organização contratante normalmente decide as finalidades do tratamento dos dados de seus integrantes e atua como controladora. A ThermoProActive trata os dados necessários à prestação da plataforma conforme o contrato e as instruções aplicáveis, sem prejuízo das responsabilidades definidas pela LGPD.</p></section>
      <section><h2>2. Dados tratados</h2><ul><li>identificação e contato, como nome, e-mail profissional, telefone e cargo;</li><li>organização, perfil de acesso e vínculos operacionais;</li><li>registros técnicos inseridos na plataforma;</li><li>dados de segurança, como sessões, eventos de autenticação, dispositivo e endereço IP protegido por hash.</li></ul><p>CPF e dados pessoais sensíveis não são solicitados no cadastro comum. Sua coleta exige finalidade específica e base legal adequada.</p></section>
      <section><h2>3. Finalidades e bases</h2><p>Os dados são usados para criar e proteger contas, executar o serviço contratado, controlar permissões, manter auditoria, prestar suporte e cumprir obrigações legais. Comunicações comerciais dependem de consentimento separado e opcional, que pode ser revogado.</p></section>
      <section><h2>4. Compartilhamento e retenção</h2><p>O acesso é limitado à organização vinculada, à equipe autorizada e a fornecedores necessários de infraestrutura ou comunicação, sujeitos a obrigações de segurança. Os dados são mantidos pelo período da relação contratual e, depois, somente pelo tempo necessário ao cumprimento de obrigações legais, defesa de direitos e segurança.</p></section>
      <section><h2>5. Segurança e tecnologias locais</h2><p>São usados controles como criptografia de transporte, cookies essenciais HttpOnly, proteção CSRF, sessões revogáveis, MFA, limitação de tentativas e trilhas de segurança. A preferência de tema pode ser mantida no armazenamento local do navegador. A plataforma não depende de cookies publicitários para autenticação.</p></section>
      <section><h2>6. Direitos do titular</h2><p>O titular pode solicitar confirmação e acesso, correção, informações sobre compartilhamento e, quando aplicável, anonimização, bloqueio, exclusão, portabilidade, oposição ou revogação do consentimento. A solicitação deve ser dirigida ao responsável pela conta ou ao canal oficial indicado no contrato da organização.</p><p>Consulte também as <Link href="https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados" target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">orientações da Autoridade Nacional de Proteção de Dados</Link>.</p></section>
      <section><h2>7. Atualizações</h2><p>Esta política pode ser atualizada para refletir mudanças legais, contratuais ou técnicas. Alterações relevantes serão comunicadas pelos canais adequados. O texto deve ser validado com a assessoria jurídica e com os contratos vigentes antes do go-live.</p></section>
    </LegalDocument>
  );
}
