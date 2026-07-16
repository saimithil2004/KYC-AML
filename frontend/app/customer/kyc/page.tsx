import { redirect } from "next/navigation";

export default function KycRedirect() {
  redirect("/customer/onboarding/kyc");
}
