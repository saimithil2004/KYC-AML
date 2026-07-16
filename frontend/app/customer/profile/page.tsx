import { redirect } from "next/navigation";

export default function ProfileRedirect() {
  redirect("/customer/onboarding/profile");
}
