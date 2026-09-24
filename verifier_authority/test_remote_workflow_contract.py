import unittest
from pathlib import Path


class RemoteVerifierWorkflowContractTests(unittest.TestCase):
    def test_remote_workflow_keeps_external_verification_contract(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "remote_verifier_authority.yml"
        ).read_text(encoding="utf-8")

        required = (
            "runs-on: ubuntu-latest",
            "id-token: write",
            "attestations: write",
            "persist-credentials: false",
            "github.event.issue.user.login == github.repository_owner",
            "actions/attest@v4",
            "--signer-workflow",
            "--source-ref refs/heads/main",
            "--deny-self-hosted-runners",
            "tampered-receipt.json",
        )
        for item in required:
            self.assertIn(item, workflow)

        forbidden = (
            "runs-on: self-hosted",
            "pull_request_target:",
            "permissions: write-all",
            "persist-credentials: true",
        )
        for item in forbidden:
            self.assertNotIn(item, workflow)


if __name__ == "__main__":
    unittest.main()
