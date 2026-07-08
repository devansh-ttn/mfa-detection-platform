"""Tests for training data loader and domain split."""

from __future__ import annotations

from mfa_ml.data.loader import LabeledSample, domain_stratified_split


def _sample(url: str, domain: str, label: int) -> LabeledSample:
    return LabeledSample(
        url=url,
        domain=domain,
        url_hash=f"hash-{domain}-{label}",
        label=label,
        features={},
        gold_label="MFA_High" if label == 1 else "Non_MFA",
    )


class TestDomainStratifiedSplit:
    def test_single_minority_domain_stays_in_train(self) -> None:
        samples = [
            _sample(f"https://mfa{i}.example/a", f"mfa{i}.example", 1)
            for i in range(10)
        ] + [
            _sample("https://www.forbes.com/", "www.forbes.com", 0),
            _sample("https://www.forbes.com/leadership/", "www.forbes.com", 0),
        ]

        split = domain_stratified_split(samples, val_fraction=0.20, random_seed=42)

        assert split.label_distribution("train")["Non_MFA"] > 0
        assert split.label_distribution("val")["MFA"] > 0

    def test_both_classes_present_in_train_when_possible(self) -> None:
        samples = [
            _sample(f"https://mfa{i}.example/a", f"mfa{i}.example", 1)
            for i in range(8)
        ] + [
            _sample("https://publisher-a.example/a", "publisher-a.example", 0),
            _sample("https://publisher-b.example/a", "publisher-b.example", 0),
        ]

        split = domain_stratified_split(samples, val_fraction=0.20, random_seed=7)

        train_dist = split.label_distribution("train")
        assert train_dist["MFA"] > 0
        assert train_dist["Non_MFA"] > 0
