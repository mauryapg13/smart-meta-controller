import os
import torch
from datasets import load_dataset, DatasetDict
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    Trainer,
    TrainingArguments,
)
from sklearn.metrics import accuracy_score, f1_score
import numpy as np

def compute_metrics(p):
    preds = np.argmax(p.predictions, axis=1)
    return {
        "accuracy": accuracy_score(p.label_ids, preds),
        "f1": f1_score(p.label_ids, preds, average="binary"),
    }

def main():
    # Load the dataset
    dataset = load_dataset("csv", data_files="data/prompts.csv")

    # Map labels
    def map_labels(examples):
        return {"label": [0 if str(l).strip().lower() == "light" else 1 for l in examples["label"]]}

    dataset = dataset.map(map_labels, batched=True)
    # Force the feature type to be int64 so PyTorch can use it
    from datasets import Value
    dataset = dataset.cast_column("label", Value("int64"))

    # Tokenizer
    tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

    def tokenize(batch):
        return tokenizer(batch["text"], padding=True, truncation=True, max_length=128)

    dataset = dataset.map(tokenize, batched=True)
    dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    # Split dataset
    train_test_split = dataset["train"].train_test_split(test_size=0.2, seed=42)
    split_dataset = DatasetDict({
        'train': train_test_split['train'],
        'test': train_test_split['test']
    })


    # Model
    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased", num_labels=2
    )

    # Training Arguments
    output_dir = "./models/distilbert-prompt-classifier"
    training_args = TrainingArguments(
        output_dir=output_dir,
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=3,
        weight_decay=0.01,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=split_dataset["train"],
        eval_dataset=split_dataset["test"],
        compute_metrics=compute_metrics,
    )

    # Train
    trainer.train()

    # Evaluate
    eval_results = trainer.evaluate()
    print(f"Evaluation results: {eval_results}")

    # Save model and tokenizer
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model and tokenizer saved to {output_dir}")

if __name__ == "__main__":
    main()
